from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Channel, ChannelEntry, FreestyleVideo


# -----------------------
# Page
# -----------------------
def tv(request):
    return render(request, "freestyle/tv.html")


# -----------------------
# Helpers
# -----------------------
def _active_channel_videos(channel_slug: str):
    """
    Returns a list of FreestyleVideo in the order they should play:
    ChannelEntry.active=True ordered by position, and only video.status='published'.
    """
    try:
        channel = Channel.objects.get(slug=channel_slug)
    except Channel.DoesNotExist:
        return []

    entries = (
        ChannelEntry.objects
        .select_related("video")
        .filter(channel=channel, active=True, video__status="published")
        .order_by("position", "id")
    )

    videos = []
    for e in entries:
        if e.video:
            videos.append(e.video)
    return videos


def _pick_live_item(videos: list[FreestyleVideo]):
    """
    Loops through videos based on UTC time and each video's duration_seconds.
    Returns (video, offset_seconds).
    """
    if not videos:
        return None, 0

    durations = [max(1, int(v.duration_seconds or 1)) for v in videos]
    total = sum(durations) or 1

    now = int(timezone.now().timestamp())
    pos = now % total

    running = 0
    for v, d in zip(videos, durations):
        if running + d > pos:
            return v, (pos - running)
        running += d

    return videos[0], 0


# -----------------------
# API
# -----------------------
@require_GET
def api_now(request, channel: str):
    """
    GET /api/freestyle/channel/<channel>/now.json

    Uses ChannelEntry ordering so *all videos you manage in admin* can play.
    """
    videos = _active_channel_videos(channel)

    # Fallback: if no channel entries exist, play all published videos by newest first.
    if not videos:
        videos = list(
            FreestyleVideo.objects.filter(status="published").order_by("-created_at", "-id")
        )

    # Ultimate fallback demo
    demo_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

    video, offset = _pick_live_item(videos)

    if video is None:
        return JsonResponse(
            {
                "item": {"video_id": "demo", "play_url": demo_url, "is_hls": False},
                "offset_seconds": 0,
            }
        )

    play_url = video.get_play_url() or demo_url
    is_hls = bool(video.is_hls())

    return JsonResponse(
        {
            "item": {
                "video_id": str(video.id),
                "play_url": play_url,
                "is_hls": is_hls,
            },
            "offset_seconds": int(offset),
        }
    )


@require_GET
def api_captions(request, video_id: int):
    """
    GET /api/freestyle/video/<video_id>/captions.json

    Returns captions_words stored on FreestyleVideo as:
      [{ "w": "word", "s": 0.123, "e": 0.456 }, ...]
    """
    try:
        v = FreestyleVideo.objects.get(id=video_id)
    except FreestyleVideo.DoesNotExist:
        return JsonResponse({"words": []})

    words = v.captions_words or []
    if not isinstance(words, list):
        words = []

    return JsonResponse({"words": words})

from django.shortcuts import render

def tv(request):
    return render(request, "freestyle/tv.html")

from django.shortcuts import render

def tv(request):
    return render(request, "freestyle/tv.html")