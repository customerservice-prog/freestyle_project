# freestyle/tv_api_views.py
from __future__ import annotations

from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Channel, ChannelEntry, ChatMessage, Presence, SponsorAd


# -------------------------
# Helpers
# -------------------------

PRESENCE_TTL_SECONDS = 90  # viewers considered "watching" if pinged recently


def _get_channel(request, channel_slug: str | None = None) -> Channel | None:
    """
    Resolve channel by:
      1) URL kwarg channel_slug (api route)
      2) ?channel=main querystring
      3) Channel.is_default
      4) first Channel
    """
    slug = (channel_slug or "").strip() or (request.GET.get("channel") or "").strip()
    if slug:
        ch = Channel.objects.filter(slug=slug).first()
        if ch:
            return ch

    ch = Channel.objects.filter(is_default=True).first()
    if ch:
        return ch

    return Channel.objects.first()


def _prune_presence(channel_obj: Channel) -> int:
    cutoff = timezone.now() - timedelta(seconds=PRESENCE_TTL_SECONDS)
    Presence.objects.filter(channel=channel_obj, last_seen__lt=cutoff).delete()
    return Presence.objects.filter(channel=channel_obj).count()


def _video_payload(v) -> dict:
    """
    IMPORTANT: Use play_url that points to /media/... (or HLS)
    We include a few alias keys so whatever JS you have will work.
    """
    play_url = getattr(v, "play_url", "") or ""
    storage_name = ""

    # If you have a FileField (video_file) we expose its name too
    video_file = getattr(v, "video_file", None)
    if video_file and getattr(video_file, "name", None):
        storage_name = video_file.name

    return {
        "id": v.id,
        "title": getattr(v, "title", "") or "",
        "duration_seconds": int(getattr(v, "duration_seconds", 0) or 0),
        "is_hls": bool(getattr(v, "is_hls", False)),
        "storage_name": storage_name,
        "play_url": play_url,

        # Back-compat aliases some frontends expect:
        "src": play_url,
        "url": play_url,
    }


def _pick_now_from_entries(channel_obj: Channel):
    """
    Build the channel playlist from active entries and pick the
    currently-playing video based on Channel.schedule_started_at.

    Returns: (current_video_or_None, seconds_into_current, playlist_video_ids, station_offset_seconds)
    """
    qs = (
        ChannelEntry.objects.filter(channel=channel_obj, is_active=True)
        .select_related("video")
        .order_by("sort_order", "id")
    )
    entries = list(qs)
    if not entries:
        return None, 0, [], 0

    videos = [e.video for e in entries]
    durations = [int(getattr(v, "duration_seconds", 0) or 0) for v in videos]

    # If durations are missing, we still return the first item with offset 0
    total = sum(d for d in durations if d > 0)
    if total <= 0:
        return videos[0], 0, [v.id for v in videos], 0

    anchor = getattr(channel_obj, "schedule_started_at", None) or timezone.now()
    station_offset = int((timezone.now() - anchor).total_seconds()) % total

    # Walk the rotation to find the current video
    acc = 0
    for v, d in zip(videos, durations):
        d = max(0, int(d))
        if d <= 0:
            continue
        if station_offset < acc + d:
            seconds_into = station_offset - acc
            return v, seconds_into, [vv.id for vv in videos], station_offset
        acc += d

    # Fallback (shouldn't happen)
    return videos[0], 0, [v.id for v in videos], station_offset


# -------------------------
# Endpoints
# -------------------------

@require_GET
def now_json(request, channel: str | None = None):
    """
    Works for BOTH:
      /now.json
      /api/freestyle/channel/<channel>/now.json

    Returns keys: now + (aliases item/current), offset_seconds, station_offset_seconds
    """
    ch = _get_channel(request, channel_slug=channel)
    if not ch:
        return JsonResponse({"ok": True, "now": None, "item": None, "current": None, "offset_seconds": 0})

    current, seconds_into, playlist_ids, station_offset = _pick_now_from_entries(ch)
    viewers = _prune_presence(ch)

    sponsor = SponsorAd.objects.filter(is_active=True).order_by("-id").first()
    sponsor_payload = None
    if sponsor:
        sponsor_payload = {
            "title": sponsor.title,
            "description": sponsor.description,
            "image_url": sponsor.image_url,
            "click_url": sponsor.click_url,
        }

    if not current:
        return JsonResponse(
            {
                "ok": True,
                "channel": ch.slug,
                "offset_seconds": 0,
                "station_offset_seconds": 0,
                "viewers": viewers,
                "sponsor": sponsor_payload,
                "playlist": playlist_ids,
                "now": None,
                "item": None,
                "current": None,
            }
        )

    payload = _video_payload(current)

    # Make sure offset_seconds is always valid for the current item if duration exists
    dur = int(payload.get("duration_seconds") or 0)
    if dur > 0:
        seconds_into = int(seconds_into) % dur
    else:
        seconds_into = 0

    return JsonResponse(
        {
            "ok": True,
            "channel": ch.slug,
            "offset_seconds": int(seconds_into),
            "station_offset_seconds": int(station_offset),
            "viewers": viewers,
            "sponsor": sponsor_payload,
            "playlist": playlist_ids,

            # Primary key the TV should use:
            "now": payload,

            # Compatibility aliases (some JS expects item/current):
            "item": payload,
            "current": payload,
        }
    )


@require_GET
def messages_json(request, channel: str | None = None):
    """
    /messages.json?after_id=0&channel=main
    """
    ch = _get_channel(request, channel_slug=channel)
    if not ch:
        return JsonResponse({"ok": True, "messages": []})

    try:
        after_id = int(request.GET.get("after_id", "0") or 0)
    except ValueError:
        after_id = 0

    qs = ChatMessage.objects.filter(channel=ch, id__gt=after_id).order_by("id")[:200]
    messages = [
        {
            "id": m.id,
            "username": m.username,
            "message": m.message,
            "created_at": m.created_at.isoformat(),
        }
        for m in qs
    ]
    return JsonResponse({"ok": True, "messages": messages})


@require_GET
def ping_json(request, channel: str | None = None):
    """
    /ping.json?sid=<uuid>&channel=main
    """
    ch = _get_channel(request, channel_slug=channel)
    if not ch:
        return JsonResponse({"ok": True, "channel": None, "server_time": timezone.now().isoformat(), "watching": None})

    sid = (request.GET.get("sid") or "").strip()
    if sid:
        Presence.objects.update_or_create(
            channel=ch,
            sid=sid,
            defaults={"last_seen": timezone.now()},
        )

    _prune_presence(ch)

    return JsonResponse(
        {
            "ok": True,
            "channel": ch.slug,
            "server_time": timezone.now().isoformat(),
            "watching": None,
        }
    )
