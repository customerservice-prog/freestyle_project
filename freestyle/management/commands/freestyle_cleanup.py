from django.core.management.base import BaseCommand
from freestyle.models import Channel
from freestyle.services.publishing import cleanup_oldest_if_played_once

class Command(BaseCommand):
    help = "Remove oldest channel entry only after it has played once."

    def handle(self, *args, **options):
        for ch in Channel.objects.all():
            removed = cleanup_oldest_if_played_once(ch)
            if removed:
                self.stdout.write(self.style.SUCCESS(f"Removed entry {removed.id} from {ch.slug}"))
            else:
                self.stdout.write(f"No removal for {ch.slug}")
