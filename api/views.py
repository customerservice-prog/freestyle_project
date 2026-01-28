from __future__ import annotations

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.db.models import Q

from freestyle.models import Channel, ChannelEntry, FreestyleVideo


def _safe_duration(v: FreestyleVideo) -> int:
    # never allow 0 (would cause rapid looping)
    try:
        d = int(v.duration_seconds or 0)
    except Exception:
        d = 0
    return max(1, d)


def _build_play_url(request, video: FreestyleVideo) -> str:
    """
    Always return an absolute URL when possible.
    - If playback_url is set, use it (works best on Render).
    - Else use video_file.url (works locally if MEDIA served; production needs persistent storage).
    """
    if video.playback_url:
        return video.playback_url

    if video.video_file:
        try:
            # Make absolute so it works on Render domain too
            return request.build_absolute_uri(video.video_file.url)
        except Exception:
            return ""

    return ""


def _get_playlist(channel: Channel):
    """
    Prefer ChannelEntries if present & active; otherwise fallback to all published/approved videos.
    """
    entries = (
        ChannelEntry.objects
        .filter(channel=channel, active=True)
        .select_related("video")
        .order_by("position", "id")
    )

    videos = [e.video for e in entries if e.video_id]

    if videos:
        return videos

    # fallback: everything that should play
    videos = list(
        FreestyleVideo.objects
        .filter(Q(status="published") | Q(status="approved"))
        .order_by("id")
    )
    return videos


def _compute_now(channel: Channel, videos: list[FreestyleVideo]):
    """
    Compute which video should be playing right now, based on a stable shared start time.
    We use channel.created_at as the start anchor so refresh NEVER resets the schedule.
    """
    if not videos:
        return None, 0

    durations = [_safe_duration(v) for v in videos]
    total = sum(durations)
    if total <= 0:
        return None, 0

    start = channel.created_at or timezone.now()
    now = timezone.now()

    elapsed = int((now - start).total_seconds())
    # position in the loop across entire playlist
    pos = elapsed % total

    # pick the current video and offset
    running = 0
    for v, d in zip(videos, durations):
        if running + d > pos:
            offset = pos - running
            return v, int(offset)
        running += d

    # fallback (shouldn't happen)
    return videos[0], 0


@require_GET
def channel_now_json(request, slug: str):
    # Guarantee channel exists; created_at becomes the stable shared start point
    channel, _ = Channel.objects.get_or_create(slug=slug, defaults={"name": slug})

    videos = _get_playlist(channel)
    video, offset = _compute_now(channel, videos)

    if not video:
        # Return 200 so frontend doesn't "alert fail"
        return JsonResponse(
            {"item": None, "offset_seconds": 0, "error": "no_videos"},
            status=200
        )

    play_url = _build_play_url(request, video)
    is_hls = (play_url.lower().endswith(".m3u8") or "m3u8" in play_url.lower())

    # If we can't build a URL, still return 200 with item=null so UI can show status
    if not play_url:
        return JsonResponse(
            {"item": None, "offset_seconds": 0, "error": f"video_{video.id}_missing_url"},
            status=200
        )

    return JsonResponse(
        {
            "item": {
                "video_id": video.id,
                "play_url": play_url,
                "is_hls": is_hls,
            },
            "offset_seconds": offset,
        },
        status=200
    )


@require_GET
def video_captions_json(request, video_id: int):
    try:
        v = FreestyleVideo.objects.get(id=video_id)
    except FreestyleVideo.DoesNotExist:
        return JsonResponse({"words": []}, status=404)

    words = v.captions_words or []
    if not isinstance(words, list):
        words = []

    return JsonResponse({"video_id": v.id, "words": words}, status=200)
