from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from freestyle.models import Channel, ChannelEntry, FreestyleVideo


@transaction.atomic
def ensure_channel(slug="main", name="Main"):
    # ✅ start_time gives the channel a "live clock"
    ch, created = Channel.objects.get_or_create(slug=slug, defaults={"name": name, "start_time": timezone.now()})
    if not created and not ch.start_time:
        ch.start_time = timezone.now()
        ch.save(update_fields=["start_time"])
    return ch


@transaction.atomic
def publish_append_to_end(video: FreestyleVideo, channel_slug="main") -> ChannelEntry:
    channel = ensure_channel(channel_slug, "Main")

    video.status = FreestyleVideo.Status.PUBLISHED
    video.save(update_fields=["status"])

    max_pos = ChannelEntry.objects.filter(channel=channel).aggregate(Max("position"))["position__max"] or 0
    entry = ChannelEntry.objects.create(
        channel=channel,
        video=video,
        position=max_pos + 1,
        active=True,
        has_played_once=False,
        added_at=timezone.now(),
    )

    cleanup_oldest_if_played_once(channel)
    return entry


@transaction.atomic
def cleanup_oldest_if_played_once(channel: Channel):
    oldest = (
        ChannelEntry.objects
        .select_for_update()
        .filter(channel=channel, active=True)
        .order_by("position", "added_at")
        .first()
    )
    if not oldest:
        return None

    if oldest.has_played_once:
        oldest.active = False
        oldest.save(update_fields=["active"])
        return oldest

    return None
