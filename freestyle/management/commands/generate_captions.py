from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Iterable

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from freestyle.models import FreestyleVideo


@dataclass
class Word:
    w: str
    s: float
    e: float


# ----------------------------
# FFmpeg discovery (robust)
# ----------------------------

def _default_ffmpeg_candidates() -> list[str]:
    """
    Common Windows locations (especially WinGet Gyan build).
    Adjust/add candidates if your machine differs.
    """
    user = os.environ.get("USERNAME") or "bryan"
    return [
        rf"C:\Users\{user}\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        rf"C:\Users\{user}\scoop\shims\ffmpeg.exe",
    ]


def _which_ffmpeg(explicit: str | None = None) -> str | None:
    """
    Priority:
      1) --ffmpeg explicit path
      2) env var FFMPEG_BIN
      3) PATH lookup (shutil.which)
      4) known fallback locations
    """
    if explicit:
        p = explicit.strip().strip('"')
        if os.path.exists(p):
            return p

    env = (os.environ.get("FFMPEG_BIN") or "").strip().strip('"')
    if env and os.path.exists(env):
        return env

    p = shutil.which("ffmpeg")
    if p:
        return p

    for c in _default_ffmpeg_candidates():
        if os.path.exists(c):
            return c

    return None


def _ffmpeg_debug_hint() -> str:
    return (
        "ffmpeg was not found.\n\n"
        "FAST FIX (this terminal):\n"
        "  $ffbin = \"C:\\Users\\bryan\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-8.0.1-full_build\\bin\"\n"
        "  $env:PATH = \"$ffbin;$env:PATH\"\n"
        "  where.exe ffmpeg\n"
        "  ffmpeg -version\n\n"
        "BULLETPROOF:\n"
        "  Pass --ffmpeg \"C:\\path\\to\\ffmpeg.exe\" or set env var FFMPEG_BIN.\n"
    )


# ----------------------------
# Process helpers
# ----------------------------

def _run(cmd: list[str], label: str = "command") -> tuple[str, str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise CommandError(
            f"{label} failed (exit {p.returncode}):\n"
            + " ".join(cmd)
            + "\n\nSTDERR:\n"
            + (p.stderr or "")
            + ("\n\nSTDOUT:\n" + (p.stdout or "") if p.stdout else "")
        )
    return (p.stdout or "", p.stderr or "")


def _extract_wav(ffmpeg: str, video_path: str, wav_path: str) -> None:
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        wav_path,
    ]
    _run(cmd, label="ffmpeg audio extract")


# ----------------------------
# Whisper helpers
# ----------------------------

def _load_whisper(model_name: str):
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise CommandError(
            "faster-whisper not installed in this venv.\n"
            "Run: pip install faster-whisper\n\n"
            f"Original error: {e}"
        )

    return WhisperModel(model_name, device="cpu", compute_type="int8")


def _consume(segments: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    for s in segments:
        out.append(s)
    return out


def _transcribe_words(
    model_name: str,
    wav_path: str,
    language: str | None,
    beam_size: int,
) -> list[Word]:
    print(f"[captions] Loading whisper model={model_name} device=cpu compute=int8 ...", flush=True)
    model = _load_whisper(model_name)

    print(f"[captions] Transcribing wav (beam={beam_size}, language={language or 'auto'}) ...", flush=True)
    segments, info = model.transcribe(
        wav_path,
        language=language,
        beam_size=beam_size,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350},
    )

    segs = _consume(segments)
    print(f"[captions] Transcribe returned {len(segs)} segments. Collecting words...", flush=True)

    out: list[Word] = []
    for seg in segs:
        words = getattr(seg, "words", None) or []
        for ww in words:
            w = (getattr(ww, "word", "") or "").strip()
            if not w:
                continue
            s = float(getattr(ww, "start", 0.0) or 0.0)
            e = float(getattr(ww, "end", s) or s)
            if e < s:
                e = s
            out.append(Word(w=w, s=s, e=e))

    print(f"[captions] Collected {len(out)} words.", flush=True)
    return out


# ----------------------------
# Django command
# ----------------------------

class Command(BaseCommand):
    help = "Generate word-level captions for a FreestyleVideo using ffmpeg + faster-whisper."

    def add_arguments(self, parser):
        parser.add_argument("--video", type=int, required=False, help="Video ID to caption.")
        parser.add_argument("--all", action="store_true", help="Caption all videos that need captions.")
        parser.add_argument("--force", action="store_true", help="Overwrite existing captions_words.")
        parser.add_argument("--model", default="small", help="tiny | base | small | medium | large-v3 (etc)")
        parser.add_argument("--language", default="", help="Optional: force language (e.g. en). Leave blank to auto.")
        parser.add_argument("--beam", type=int, default=5, help="Beam size (quality vs speed). Default 5.")
        parser.add_argument("--ffmpeg", default="", help="Optional: full path to ffmpeg.exe (overrides PATH).")

    def handle(self, *args, **opts):
        ffmpeg_arg = (opts.get("ffmpeg") or "").strip() or None
        ffmpeg = _which_ffmpeg(ffmpeg_arg)
        if not ffmpeg:
            raise CommandError(_ffmpeg_debug_hint())

        # sanity: ensure ffmpeg can run
        _run([ffmpeg, "-version"], label="ffmpeg -version")

        force: bool = bool(opts["force"])
        model_name: str = str(opts["model"])
        language = (opts.get("language") or "").strip() or None
        beam_size: int = int(opts.get("beam") or 5)

        qs = FreestyleVideo.objects.all().order_by("id")

        if opts.get("video"):
            qs = qs.filter(id=int(opts["video"]))
        elif opts.get("all"):
            qs = qs
        else:
            raise CommandError("Provide --video <id> or --all")

        total = int(qs.count())
        self.stdout.write(f"Generate captions: total candidates = {total}")
        self.stdout.write(f"Using ffmpeg: {ffmpeg}")
        self.stdout.write(f"Using model: {model_name} | beam: {beam_size} | language: {language or 'auto'}")

        # What fields actually exist on this model?
        model_field_names = {f.name for f in FreestyleVideo._meta.get_fields()}
        has_captions_model = "captions_model" in model_field_names
        has_captions_updated_at = "captions_updated_at" in model_field_names

        updated = 0
        skipped = 0
        failed = 0

        for v in qs:
            title = getattr(v, "title", "")
            existing = (getattr(v, "captions_words", None) or [])
            if existing and not force:
                self.stdout.write(f"SKIP id={v.id} '{title}' (already has captions)")
                skipped += 1
                continue

            if not getattr(v, "video_file", None):
                self.stdout.write(f"FAIL id={v.id} '{title}' (no local video_file)")
                failed += 1
                continue

            try:
                video_path = v.video_file.path
            except Exception:
                self.stdout.write(f"FAIL id={v.id} '{title}' (video_file has no local path)")
                failed += 1
                continue

            if not os.path.exists(video_path):
                self.stdout.write(f"FAIL id={v.id} '{title}' (missing file on disk)")
                failed += 1
                continue

            self.stdout.write("\n---")
            self.stdout.write(f"VIDEO id={v.id} '{title}'")
            self.stdout.write(f"Path: {video_path}")
            self.stdout.flush()

            try:
                with tempfile.TemporaryDirectory() as td:
                    wav_path = os.path.join(td, f"v{v.id}.wav")

                    self.stdout.write("Extracting wav with ffmpeg...")
                    self.stdout.flush()
                    _extract_wav(ffmpeg, video_path, wav_path)

                    self.stdout.write("Wav extracted. Running whisper...")
                    self.stdout.flush()
                    words = _transcribe_words(
                        model_name=model_name,
                        wav_path=wav_path,
                        language=language,
                        beam_size=beam_size,
                    )

                payload: list[dict[str, Any]] = [{"w": w.w, "s": w.s, "e": w.e} for w in words]

                # Save only what exists on the model
                v.captions_words = payload
                update_fields = ["captions_words"]

                if has_captions_model:
                    v.captions_model = model_name
                    update_fields.append("captions_model")

                if has_captions_updated_at:
                    v.captions_updated_at = timezone.now()
                    update_fields.append("captions_updated_at")

                v.save(update_fields=update_fields)

                self.stdout.write(f"OK id={v.id} words={len(payload)}")
                updated += 1

            except KeyboardInterrupt:
                raise

            except Exception as e:
                self.stdout.write(f"FAIL id={v.id} '{title}' => {e}")
                failed += 1

        self.stdout.write("\n=== SUMMARY ===")
        self.stdout.write(f"Updated:   {updated}")
        self.stdout.write(f"Skipped:   {skipped}")
        self.stdout.write(f"Failed:    {failed}")
