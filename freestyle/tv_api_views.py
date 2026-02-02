# freestyle/tv_api_views.py
from __future__ import annotations

from typing import Any, Optional

from django.http import JsonResponse, HttpRequest
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.db import transaction

from .models import Channel, ChannelEntry, FreestyleVideo

# These imports are optional depending on your models. We import safely.
try:
    from .models import ChatMessage  # type: ignore
except Exception:
    ChatMessage = None  # type: ignore

try:
    from .models import Presence  # type: ignore
except Exception:
    Presence = None  # type: ignore


# -----------------------------
# Helpers
# -----------------------------
def _iso(dt):
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


def _safe_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default


def _get_channel_slug(request: HttpRequest, channel: Optional[str] = None) -> str:
    # Priority: URL param -> querystring -> header -> default
    return (
        (channel or "").strip()
        or (request.GET.get("channel") or "").strip()
        or (request.headers.get("X-Channel") or "").strip()
        or "main"
    )


def _get_channel(slug: str) -> Channel:
    # Ensure channel exists
    obj, _ = Channel.objects.get_or_create(slug=slug, defaults={"name": slug.title()})
    return obj


def _video_name_and_url(video: FreestyleVideo) -> tuple[Optional[str], Optional[str]]:
    """
    Works whether video_file is FileField or null.
    Returns (storage_name, absolute_media_url_relative).
    """
    name = None
    url = None

    vf = getattr(video, "video_file", None)
    if vf:
        # FileField -> FieldFile; printing shows name, .url builds MEDIA_URL path
        try:
            name = vf.name
        except Exception:
            name = None
        try:
            url = vf.url
        except Exception:
            url = None

    # Legacy fallback if you ever had 'file' in older schema
    if not url:
        f = getattr(video, "file", None)
        if f:
            try:
                name = getattr(f, "name", None) or name
            except Exception:
                pass
            try:
                url = f.url
            except Exception:
                pass

    # Another fallback: some old DBs store a plain string path
    if not url and isinstance(vf, str) and vf.strip():
        name = vf.strip()
        url = "/media/" + name.lstrip("/")

    return name, url


def _duration_seconds(video: FreestyleVideo) -> int:
    d = getattr(video, "duration_seconds", None)
    d = _safe_int(d, 0)
    # If missing, assume 180 seconds so rotation still works
    return d if d > 0 else 180


def _serialize_video(video: FreestyleVideo, seconds_into: int = 0) -> dict[str, Any]:
    storage_name, media_url = _video_name_and_url(video)

    is_hls = bool(getattr(video, "is_hls", False))
    play_url = getattr(video, "play_url", None)  # some schemas had this
    if not play_url:
        play_url = media_url

    return {
        "id": video.id,
        "title": getattr(video, "title", "") or "",
        "is_hls": is_hls,
        "duration_seconds": _duration_seconds(video),
        "seconds_into": max(0, _safe_int(seconds_into, 0)),
        # URLs (redundant on purpose so your frontend can use any key it expects)
        "play_url": play_url,
        "video_url": play_url,
        "mp4_url": media_url if not is_hls else None,
        "hls_url": media_url if is_hls else None,
        # debug/helpful
        "storage_name": storage_name,
    }


def _pick_now_from_entries(channel_obj: Channel) -> tuple[Optional[FreestyleVideo], int, list[FreestyleVideo]]:
    """
    Returns (current_video, seconds_into, playlist_videos)
    Uses Channel.rotation_started_at as the start of the loop.
    """
    qs = (
        ChannelEntry.objects.filter(channel=channel_obj, is_active=True)
        .select_related("video")
        .order_by("sort_order", "id")
    )
    entries = list(qs)
    videos = [e.video for e in entries if getattr(e, "video_id", None)]

    if not videos:
        # fallback: any videos at all
        any_vid = FreestyleVideo.objects.order_by("id").first()
        return any_vid, 0, ([any_vid] if any_vid else [])

    # Ensure rotation_started_at exists
    if not getattr(channel_obj, "rotation_started_at", None):
        channel_obj.rotation_started_at = timezone.now()
        channel_obj.save(update_fields=["rotation_started_at"])

    started = channel_obj.rotation_started_at
    now = timezone.now()

    elapsed = int((now - started).total_seconds())
    durations = [_duration_seconds(v) for v in videos]
    total = sum(durations) or 1
    pos = elapsed % total

    running = 0
    current = videos[0]
    seconds_into = 0

    for v, d in zip(videos, durations):
        if pos < running + d:
            current = v
            seconds_into = pos - running
            break
        running += d

    return current, seconds_into, videos


# -----------------------------
# Endpoints
# -----------------------------
@require_GET
def now_json(request: HttpRequest, channel: Optional[str] = None):
    """
    Works for BOTH:
      - /now.json
      - /api/freestyle/channel/<slug>/now.json  (we route this to here)
    """
    slug = _get_channel_slug(request, channel)
    ch = _get_channel(slug)

    current, seconds_into, playlist = _pick_now_from_entries(ch)

    payload = {
        "ok": True,
        "channel": slug,
        "server_time": _iso(timezone.now()),
        "rotation_started_at": _iso(getattr(ch, "rotation_started_at", None)),
        "watching": None,  # filled by ping.json if Presence is enabled
        "now": _serialize_video(current, seconds_into) if current else None,
        # also return a simple flat shape for older JS
        "id": current.id if current else None,
        "title": getattr(current, "title", "") if current else "",
        "play_url": _serialize_video(current, seconds_into).get("play_url") if current else None,
        "seconds_into": seconds_into if current else 0,
        "queue": [_serialize_video(v, 0) for v in playlist[:50]],
    }
    return JsonResponse(payload)


@require_GET
def messages_json(request: HttpRequest, channel: Optional[str] = None):
    """
    /messages.json?after_id=0
    Returns a list of messages newer than after_id.
    If ChatMessage model doesn't exist, returns empty list.
    """
    after_id = _safe_int(request.GET.get("after_id"), 0)

    if ChatMessage is None:
        return JsonResponse({"ok": True, "messages": []})

    slug = _get_channel_slug(request, channel)
    ch = _get_channel(slug)

    qs = ChatMessage.objects.all()

    # Try to filter by channel if field exists
    if hasattr(ChatMessage, "channel_id"):
        qs = qs.filter(channel=ch)

    if after_id:
        qs = qs.filter(id__gt=after_id)

    qs = qs.order_by("id")[:200]

    out = []
    for m in qs:
        out.append(
            {
                "id": m.id,
                "user": getattr(m, "user_name", None)
                or getattr(getattr(m, "user", None), "username", None)
                or getattr(m, "username", None)
                or "anon",
                "text": getattr(m, "text", None) or getattr(m, "message", None) or "",
                "created_at": _iso(getattr(m, "created_at", None) or getattr(m, "timestamp", None)),
            }
        )

    return JsonResponse({"ok": True, "messages": out})


@require_GET
def ping_json(request: HttpRequest, channel: Optional[str] = None):
    """
    /ping.json?sid=<session-id>
    Updates presence and returns watching count.
    If Presence model doesn't exist, returns ok + watching=None.
    """
    slug = _get_channel_slug(request, channel)
    ch = _get_channel(slug)

    sid = (request.GET.get("sid") or "").strip()
    now = timezone.now()

    watching = None

    if Presence is not None:
        # Try to record/update presence
        try:
            with transaction.atomic():
                if sid:
                    obj, created = Presence.objects.get_or_create(
                        channel=ch,
                        sid=sid,
                        defaults={"last_seen_at": now},
                    )
                    if not created:
                        obj.last_seen_at = now
                        obj.save(update_fields=["last_seen_at"])

                # prune old
                cutoff = now - timezone.timedelta(seconds=60)
                Presence.objects.filter(channel=ch, last_seen_at__lt=cutoff).delete()

                watching = Presence.objects.filter(channel=ch).count()
        except Exception:
            watching = None

    return JsonResponse(
        {
            "ok": True,
            "channel": slug,
            "server_time": _iso(now),
            "watching": watching,
        }
    )
