import json
import subprocess

from django.core.management.base import BaseCommand
from freestyle.models import FreestyleVideo


def probe_duration_seconds(path: str) -> int:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    out = subprocess.check_output(cmd, universal_newlines=True)
    data = json.loads(out)
    dur = float(data["format"]["duration"])
    return max(1, int(round(dur)))


class Command(BaseCommand):
    help = "Fill/overwrite duration_seconds for FreestyleVideo using ffprobe."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Overwrite existing duration_seconds")

    def handle(self, *args, **opts):
        force = bool(opts["force"])

        updated = 0
        skipped = 0
        failed = 0

        qs = FreestyleVideo.objects.all()

        for v in qs:
            if not getattr(v, "video_file", None) or not v.video_file:
                skipped += 1
                continue

            if not force and getattr(v, "duration_seconds", 0) and int(v.duration_seconds) > 0:
                skipped += 1
                continue

            try:
                dur = probe_duration_seconds(v.video_file.path)
                v.duration_seconds = dur
                v.save(update_fields=["duration_seconds"])
                updated += 1
                self.stdout.write(f"OK id={v.id} duration={dur}s")
            except Exception as e:
                failed += 1
                self.stderr.write(f"FAIL id={getattr(v,'id','?')} {e}")

        self.stdout.write(self.style.SUCCESS(f"Updated={updated} Skipped={skipped} Failed={failed}"))
