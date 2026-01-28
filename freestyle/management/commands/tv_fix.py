import os
import json
import subprocess
import shutil
import struct

from django.core.management.base import BaseCommand
from django.conf import settings

from freestyle.models import Channel, ChannelEntry, FreestyleVideo


# -----------------------------
# Utilities
# -----------------------------
def file_exists_for(video: FreestyleVideo) -> bool:
    if not getattr(video, "video_file", None):
        return False
    try:
        path = video.video_file.path
    except Exception:
        return False
    return bool(path) and os.path.exists(path)


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def ffprobe_duration_seconds(path: str) -> int | None:
    """
    Returns duration in seconds if ffprobe is available; otherwise None.
    """
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
            universal_newlines=True,
        )
        data = json.loads(out)
        dur = float(data["format"]["duration"])
        return max(1, int(round(dur)))
    except Exception:
        return None


def _read_u32(f):
    b = f.read(4)
    if len(b) != 4:
        return None
    return struct.unpack(">I", b)[0]


def _read_u64(f):
    b = f.read(8)
    if len(b) != 8:
        return None
    return struct.unpack(">Q", b)[0]


def _read_atom_header(f):
    """
    Returns (atom_type, atom_size, header_size) or (None, None, None) on EOF.
    """
    start = f.tell()
    size = _read_u32(f)
    if size is None:
        return None, None, None
    atype = f.read(4)
    if len(atype) != 4:
        return None, None, None
    atype = atype.decode("latin1")
    header = 8

    if size == 1:
        size64 = _read_u64(f)
        if size64 is None:
            return None, None, None
        size = size64
        header = 16

    if size < header:
        return None, None, None

    return atype, int(size), header


def mp4_duration_seconds(path: str) -> int | None:
    """
    Pure-Python MP4 duration from moov/mvhd.
    Works for standard MP4/MOV. No ffmpeg needed.
    Returns seconds or None if not found.
    """
    try:
        with open(path, "rb") as f:
            # Walk top-level atoms until we find 'moov'
            while True:
                atype, size, header = _read_atom_header(f)
                if atype is None:
                    break

                payload_start = f.tell()
                payload_size = size - header

                if atype == "moov":
                    # Read moov payload into memory (usually small)
                    moov = f.read(payload_size)
                    return _mvhd_duration_from_moov_bytes(moov)

                # Skip this atom
                f.seek(payload_start + payload_size)
    except Exception:
        return None

    return None


def _mvhd_duration_from_moov_bytes(moov: bytes) -> int | None:
    """
    Parse nested atoms inside moov to find mvhd and compute seconds.
    """
    i = 0
    n = len(moov)

    def read_u32(buf, off):
        if off + 4 > len(buf):
            return None
        return struct.unpack(">I", buf[off:off+4])[0]

    def read_u64(buf, off):
        if off + 8 > len(buf):
            return None
        return struct.unpack(">Q", buf[off:off+8])[0]

    while i + 8 <= n:
        size = read_u32(moov, i)
        if size is None:
            return None
        atype = moov[i+4:i+8].decode("latin1")
        header = 8
        if size == 1:
            size64 = read_u64(moov, i+8)
            if size64 is None:
                return None
            size = size64
            header = 16

        if size < header or i + size > n:
            return None

        if atype == "mvhd":
            mvhd = moov[i+header:i+size]
            if len(mvhd) < 16:
                return None

            version = mvhd[0]
            # flags = mvhd[1:4]

            if version == 0:
                # creation(4) mod(4) timescale(4) duration(4)
                if len(mvhd) < 4 + 4 + 4 + 4 + 4:
                    return None
                timescale = struct.unpack(">I", mvhd[12:16])[0]
                duration = struct.unpack(">I", mvhd[16:20])[0]
            else:
                # version 1: creation(8) mod(8) timescale(4) duration(8)
                if len(mvhd) < 4 + 8 + 8 + 4 + 8:
                    return None
                timescale = struct.unpack(">I", mvhd[20:24])[0]
                duration = struct.unpack(">Q", mvhd[24:32])[0]

            if timescale <= 0:
                return None
            sec = int(round(duration / timescale))
            return max(1, sec)

        i += int(size)

    return None


def best_duration_seconds(path: str) -> tuple[int | None, str]:
    """
    Try ffprobe first (if available), otherwise MP4 parser.
    Returns (seconds or None, method string).
    """
    if ffprobe_available():
        dur = ffprobe_duration_seconds(path)
        if dur is not None:
            return dur, "ffprobe"
    dur = mp4_duration_seconds(path)
    if dur is not None:
        return dur, "mp4-mvhd"
    return None, "none"


# -----------------------------
# Command
# -----------------------------
class Command(BaseCommand):
    help = (
        "Fix Live TV by disabling ChannelEntry items with missing files (and no playback_url). "
        "Optionally re-probe duration_seconds for existing files. "
        "Works without ffmpeg (MP4 parser fallback)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--channel", default="main", help="Channel slug to fix (default: main)")
        parser.add_argument("--reprobe", action="store_true", help="Recalculate duration_seconds for existing files.")
        parser.add_argument(
            "--fix30",
            action="store_true",
            help="Only overwrite duration_seconds when it's 30 (common bad value) (use with --reprobe).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show changes but do not write DB.")

    def handle(self, *args, **opts):
        slug = opts["channel"]
        reprobe = bool(opts["reprobe"])
        fix30 = bool(opts["fix30"])
        dry = bool(opts["dry_run"])

        channel = Channel.objects.filter(slug=slug).first()
        if not channel:
            self.stderr.write(f"Channel not found: slug={slug}")
            return

        entries = (
            ChannelEntry.objects
            .filter(channel=channel)
            .select_related("video")
            .order_by("position", "id")
        )

        total = entries.count()
        missing_file_entries = 0
        deactivated = 0
        duration_updated = 0
        duration_skipped = 0

        self.stdout.write(f"TV FIX running on channel='{slug}'")
        self.stdout.write(f"MEDIA_ROOT = {getattr(settings, 'MEDIA_ROOT', '')}")
        self.stdout.write(f"Total entries: {total}")
        if reprobe:
            self.stdout.write(f"Duration probe mode: ON (method: {'ffprobe' if ffprobe_available() else 'mp4-mvhd fallback'})")
        self.stdout.write("")

        for e in entries:
            v: FreestyleVideo = e.video

            exists = file_exists_for(v)
            has_playback_url = bool(getattr(v, "playback_url", "") or "")

            # Broken if local file missing AND no external URL
            if not exists and not has_playback_url:
                missing_file_entries += 1
                if e.active:
                    msg = f"DEACTIVATE entry_id={e.id} video_id={v.id} title='{getattr(v,'title','')}' (missing file, no playback_url)"
                    if dry:
                        self.stdout.write("[DRY] " + msg)
                    else:
                        e.active = False
                        e.save(update_fields=["active"])
                        self.stdout.write(msg)
                    deactivated += 1
                continue

            # Reprobe durations
            if reprobe and exists:
                try:
                    path = v.video_file.path
                except Exception:
                    duration_skipped += 1
                    continue

                current = int(getattr(v, "duration_seconds", 0) or 0)
                if fix30 and current != 30:
                    duration_skipped += 1
                    continue

                dur, method = best_duration_seconds(path)
                if dur is None:
                    duration_skipped += 1
                    continue

                if dur != current:
                    msg = f"DURATION video_id={v.id} {current}s -> {dur}s ({method})"
                    if dry:
                        self.stdout.write("[DRY] " + msg)
                    else:
                        v.duration_seconds = dur
                        v.save(update_fields=["duration_seconds"])
                        self.stdout.write(msg)
                    duration_updated += 1
                else:
                    duration_skipped += 1

        self.stdout.write("")
        self.stdout.write("=== SUMMARY ===")
        self.stdout.write(f"Entries total: {total}")
        self.stdout.write(f"Broken entries found (missing file and no playback_url): {missing_file_entries}")
        self.stdout.write(f"Entries deactivated: {deactivated}")
        self.stdout.write(f"Durations updated: {duration_updated}")
        self.stdout.write(f"Durations skipped: {duration_skipped}")
        self.stdout.write("DRY-RUN ONLY (no DB changes were saved)" if dry else "CHANGES APPLIED")
