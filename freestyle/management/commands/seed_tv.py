from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path

from freestyle.models import Channel, FreestyleVideo, ChannelVideo

class Command(BaseCommand):
    help = "Create main channel and import media/freestyle_videos into admin + playlist"

    def handle(self, *args, **opts):
        ch, _ = Channel.objects.get_or_create(slug="main", defaults={"name":"Live TV"})

        base = Path(settings.MEDIA_ROOT) / "freestyle_videos"
        base.mkdir(parents=True, exist_ok=True)

        files = sorted([p for p in base.glob("*") if p.is_file()])
        if not files:
            self.stdout.write(self.style.WARNING("No files found in media/freestyle_videos"))
            return

        order = 0
        for p in files:
            rel = f"freestyle_videos/{p.name}"
            v, _ = FreestyleVideo.objects.get_or_create(file=rel, defaults={"title": p.stem})
            ChannelVideo.objects.get_or_create(channel=ch, video=v, defaults={"order": order})
            order += 10

        self.stdout.write(self.style.SUCCESS("Seeded main channel playlist."))
