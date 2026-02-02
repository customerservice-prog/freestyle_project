# freestyle/tv_api_views.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple

from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponseNotAllowed
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Channel, ChannelEntry, ChatMessage, Presence


# -------------------------
# Helpers
# -------------------------

def _get_channel(slug: str) -> Channel:
    # If slug is missing/blank, default to "main"
    slug = (slug or "main").strip() or "main"

    # Prefer exact slug, else fallback to default channel if you have one, else create "main"
    ch = Channel.objects.filter(slug=slug).first()
    if ch:
        return ch

    ch = Channel.objects.filter(is_default=True).first()
    if ch:
        return ch

    # last resort: create "main"
    ch = Channel.objects.create(slug="main", name="Main", is_default=True)
    return ch


def _channel_anchor_dt(channel_obj: Channel):
    """
    A stable time anchor for the station clock.
    We support either:
      - schedule_started_at (newer model)
      - rotation_started_at (older model)
    """
    if hasattr(channel_obj, "schedule_started_at"):
        dt = getattr(channel_obj, "schedule_started_at", None)
        return dt or timezone.now()

    if hasattr(channel_obj, "rotation_started_at"):
        dt = getattr(channel_obj, "rotation_started_at", None)
        return dt or timezone.now()

    return timezone.now()


def _video_fieldfile(obj, field_name: str):
    """
    Returns a FieldFile (or None) if obj has a FileField with that name.
    """
    if not hasattr(obj, field_name):
        return None
    f = getattr(obj, field_name, None)
    # f might be FieldFile or None
    return f


def _video_storage_name(video) -> Optional[str]:
    """
    Prefer DB file fields:
      - video.video_file.name
      - video.file.name
    Fallback:
      - video.play_url (if it's a /media/... path, strip MEDIA_URL)
    """
    vf = _video_fieldfile(video, "video_file")
    if vf and getattr(vf, "name", None):
        return vf.name

    f = _video_fieldfile(video, "file")
    if f and getattr(f, "name", None):
        return f.name

    play_url = getattr(video, "play_url", "") or ""
    media_url = getattr(settings, "MEDIA_URL", "/media/")
    if play_url.startswith(media_url):
        return play_url[len(media_url):].lstrip("/")

    return None


def _video_is_hls(video) -> bool:
    if bool(getattr(video, "is_hls", False)):
        return True
    play_url = (getattr(video, "play_url", "") or "").lower()
    return play_url.endswith(".m3u8")


def _video_play_url(video) -> Optional[str]:
    """
    Build the URL the browser should play.
    - If HLS: prefer video.play_url (should be .m3u8)
    - Else: return /media/<storage_name>
    """
    media_url = getattr(settings, "MEDIA_URL", "/media/")
    play_url = getattr(video, "play_url", "") or ""

    if _video_is_hls(video):
        # For HLS, play_url should already be a valid URL/path.
        return play_url or None

    storage_name = _video_storage_name(video)
    if storage_name:
        # Ensure exactly one slash between MEDIA_URL and storage path
        return f"{media_url.rstrip('/')}/{storage_name.lstrip('/')}"
    return None


def _video_duration(video) -> int:
    # Duration can be 0 in DB if not filled; return 0 (we handle later)
    try:
        return int(getattr(video, "duration_seconds", 0) or 0)
    except Exception:
        return 0


def _active_entries(channel_obj: Channel) -> List[ChannelEntry]:
    return list(
        ChannelEntry.objects.filter(channel=channel_obj, is_active=True)
        .select_related("video")
        .order_by("sort_order", "id")
    )


@dataclass
class Picked:
    entry: ChannelEntry
    video: object
    seconds_into_video: int
    playlist_ids: List[int]
    station_offset_seconds: int


def _pick_now_from_entries(channel_obj: Channel) -> Optional[Picked]:
    entries = _active_entries(channel_obj)
    if not entries:
        return None

    anchor = _channel_anchor_dt(channel_obj)
    station_offset = max(0, int((timezone.now() - anchor).total_seconds()))

    # Live stream (if any active entry is marked live)
    live_entry = next((e for e in entries if getattr(e, "is_live", False)), None)
    if live_entry:
        return Picked(
            entry=live_entry,
            video=live_entry.video,
            seconds_into_video=0,
            playlist_ids=[e.video_id for e in entries],
            station_offset_seconds=station_offset,
        )

    # Rotation (MP4s)
    durations = []
    for e in entries:
        d = _video_duration(e.video)
        # If duration missing, assume 180s so rotation still works
        durations.append(d if d > 0 else 180)

    total = sum(durations)
    if total <= 0:
        # If everything is broken, just pick first
        return Picked(
            entry=entries[0],
            video=entries[0].video,
            seconds_into_video=0,
            playlist_ids=[e.video_id for e in entries],
            station_offset_seconds=station_offset,
        )

    pos = station_offset % total
    running = 0
    for e, d in zip(entries, durations):
        if pos < running + d:
            seconds_into = max(0, pos - running)
            return Picked(
                entry=e,
                video=e.video,
                seconds_into_video=int(seconds_into),
                playlist_ids=[x.video_id for x in entries],
                station_offset_seconds=station_offset,
            )
        running += d

    # Fallback (should not happen)
    return Picked(
        entry=entries[0],
        video=entries[0].video,
        seconds_into_video=0,
        playlist_ids=[e.video_id for e in entries],
        station_offset_seconds=station_offset,
    )


def _viewer_count_estimate(channel_slug: str) -> int:
    """
    Cheap placeholder — your earlier logs show you sometimes used a fake count like 1100.
    If you want "real" viewers, you can count Presence active in last N seconds.
    """
    # Active viewers in last 60s
    cutoff = timezone.now() - timezone.timedelta(seconds=60)
    try:
        return Presence.objects.filter(channel__slug=channel_slug, last_seen__gte=cutoff).count()
    except Exception:
        return 0


# -------------------------
# Endpoints expected by TV
# -------------------------

@require_GET
def now_json(request: HttpRequest, channel: Optional[str] = None):
    """
    Supports BOTH:
      - /now.json?channel=main
      - /api/freestyle/channel/main/now.json  (url kwarg: channel="main")
    """
    slug = channel or request.GET.get("channel") or "main"
    ch = _get_channel(slug)

    picked = _pick_now_from_entries(ch)
    if not picked:
        return JsonResponse(
            {
                "ok": True,
                "channel": ch.slug,
                "offset_seconds": 0,
                "now": None,
                "playlist": [],
                "viewers": _viewer_count_estimate(ch.slug),
                "sponsor": None,
            }
        )

    v = picked.video
    play_url = _video_play_url(v)
    storage_name = _video_storage_name(v)

    payload = {
        "ok": True,
        "channel": ch.slug,

        # ✅ IMPORTANT: seconds into CURRENT video (must be < duration)
        "offset_seconds": int(picked.seconds_into_video),

        # optional debug (does NOT drive the player)
        "station_offset_seconds": int(picked.station_offset_seconds),

        "viewers": _viewer_count_estimate(ch.slug),
        "sponsor": None,
        "playlist": picked.playlist_ids,

        "now": {
            "id": getattr(v, "id", None),
            "title": getattr(v, "title", "") or "",
            "duration_seconds": int(_video_duration(v) or 0),
            "is_hls": bool(_video_is_hls(v)),
            "storage_name": storage_name,
            "play_url": play_url,
            "artwork_url": getattr(v, "artwork_url", "") or "",
        },
    }
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})


@require_GET
def messages_json(request: HttpRequest):
    """
    /messages.json?after_id=0&channel=main
    """
    slug = request.GET.get("channel") or "main"
    after_id = request.GET.get("after_id") or "0"
    try:
        after_id_int = int(after_id)
    except Exception:
        after_id_int = 0

    ch = _get_channel(slug)
    qs = ChatMessage.objects.filter(channel=ch, id__gt=after_id_int).order_by("id")[:200]

    messages = []
    for m in qs:
        messages.append(
            {
                "id": m.id,
                "username": m.username,
                "message": m.message,
                "created_at": m.created_at.isoformat(),
            }
        )

    return JsonResponse({"ok": True, "messages": messages}, json_dumps_params={"ensure_ascii": False})


@require_GET
def ping_json(request: HttpRequest):
    """
    /ping.json?sid=<client_id>&channel=main
    """
    sid = (request.GET.get("sid") or "").strip()
    slug = (request.GET.get("channel") or "main").strip() or "main"

    ch = _get_channel(slug)

    if sid:
        # Update presence
        Presence.objects.update_or_create(
            channel=ch,
            sid=sid,
            defaults={"last_seen": timezone.now()},
        )

    # Optionally, return who they're watching, etc. We keep it simple.
    return JsonResponse(
        {
            "ok": True,
            "channel": ch.slug,
            "server_time": timezone.now().isoformat(),
            "watching": None,
        },
        json_dumps_params={"ensure_ascii": False},
    )
