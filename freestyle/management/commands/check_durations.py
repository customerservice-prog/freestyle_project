from django.core.management.base import BaseCommand
from freestyle.models import ChannelEntry


class Command(BaseCommand):
    help = "Print duration_seconds + file availability for the video model used by ChannelEntry.video"

    def handle(self, *args, **opts):
        VideoModel = ChannelEntry._meta.get_field("video").related_model

        file_field_name = None
        for candidate in ("video_file", "file", "media_file", "source_file"):
            if hasattr(VideoModel, candidate):
                file_field_name = candidate
                break

        self.stdout.write(f"Video model: {VideoModel.__name__}")
        self.stdout.write(f"File field: {file_field_name or 'NOT FOUND'}")
        self.stdout.write(f"Has duration_seconds: {'YES' if hasattr(VideoModel,'duration_seconds') else 'NO'}")
        self.stdout.write("")

        bad = 0
        total = 0

        for v in VideoModel.objects.all():
            total += 1
            dur = getattr(v, "duration_seconds", None)

            has_file = False
            path = ""
            if file_field_name:
                f = getattr(v, file_field_name, None)
                if f:
                    try:
                        path = f.path
                        has_file = True
                    except Exception:
                        has_file = False

            if not dur or int(dur) <= 0:
                bad += 1
                self.stdout.write(f"BAD duration id={v.id} duration_seconds={dur} has_file={has_file} path={path}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Total videos: {total} | Bad/missing duration_seconds: {bad}"))
