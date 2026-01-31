# freestyle/management/commands/fill_video_durations.py
import math
from django.core.management.base import BaseCommand
from freestyle.models import FreestyleVideo

def mp4_duration_seconds(path: str) -> int:
    try:
        from mutagen.mp4 import MP4
        length = MP4(path).info.length
        if not length:
            return 0
        return int(math.ceil(float(length)))
    except Exception:
        return 0

class Command(BaseCommand):
    help = "Fill duration_seconds for FreestyleVideo rows where duration_seconds is 0."

    def handle(self, *args, **options):
        updated = 0
        failed = 0

        qs = FreestyleVideo.objects.all().order_by("id")
        for v in qs:
            if not v.file:
                continue
            if v.duration_seconds and v.duration_seconds > 0:
                continue

            try:
                secs = mp4_duration_seconds(v.file.path)
                if secs > 0:
                    v.duration_seconds = secs
                    v.save(update_fields=["duration_seconds"])
                    updated += 1
                    self.stdout.write(f"OK  id={v.id}  secs={secs}  title={v.title}")
                else:
                    failed += 1
                    self.stdout.write(f"FAIL id={v.id}  (duration 0)  title={v.title}")
            except Exception as e:
                failed += 1
                self.stdout.write(f"FAIL id={v.id}  err={e}")

        self.stdout.write(self.style.SUCCESS(f"Done. Updated={updated}, Failed={failed}"))
