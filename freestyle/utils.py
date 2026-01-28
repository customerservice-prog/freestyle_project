from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import Channel, ChannelEntry, CreatorProfile, FreestyleVideo


def get_or_create_main_channel():
    channel, _ = Channel.objects.get_or_create(slug="main", defaults={"name": "Main"})
    return channel


@transaction.atomic
def publish_video_to_channel(video: FreestyleVideo, channel: Channel):
    video.status = FreestyleVideo.STATUS_PUBLISHED
    video.published_at = timezone.now()
    video.save()

    last = (
        ChannelEntry.objects.filter(channel=channel)
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    next_pos = (last or 0) + 1

    entry = ChannelEntry.objects.create(
        channel=channel,
        video=video,
        position=next_pos,
        active=True,
        has_played_once=False,
        added_at=timezone.now(),
    )
    return entry


def ensure_creator_for_email(email: str):
    username = email.split("@")[0]
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"username": username},
    )

    # If username already exists, fallback to email as username
    if created is False and user.username != username and not user.username:
        user.username = username
        user.save()

    profile, _ = CreatorProfile.objects.get_or_create(user=user)
    return user, profile
