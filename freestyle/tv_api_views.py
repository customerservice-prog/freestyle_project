# freestyle/tv_api_views.py
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


def _channel_slug(request, channel_kw: Optional[str] = None) -> str:
    if channel_kw:
        return str(channel_kw).strip() or "main"
    return (request.GET.get("channel") or "main").strip() or "main"


def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _media_join(storage_name: str) -> str:
    base = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").strip()
    if not base.endswith("/"):
        base += "/"
    return base + storage_name.lstrip("/")


def _extract_storage_and_url(video_obj) -> Tuple[Optional[str], Optional[str]]:
    """
    Supports BOTH schema styles:
    - Postgres "varchar" path: video.video_file == 'freestyle_videos/x.mp4'
    - Django FileField: video.video_file.name + video.video_file.url
    Also supports legacy field 'file' if it exists.
    Also supports 'play_url' external URL if present.
    """
    if not video_obj:
        return None, None

    play_url = getattr(video_obj, "play_url", None)
    if isinstance(play_url, str) and play_url.strip():
        return None, play_url.strip()

    vf = getattr(video_obj, "video_file", None)

    # Production: video_file stored as string path
    if isinstance(vf, str) and vf.strip():
        storage = vf.strip()
        return storage, _media_join(storage)

    # Dev/FileField: video_file is FieldFile
    if vf is not None and hasattr(vf, "name"):
        storage = getattr(vf, "name", None) or None
        url = getattr(vf, "url", None) or None
        if storage and url:
            return storage, url
        if storage:
            return storage, _media_join(storage)

    # Legacy fallback
    legacy = getattr(video_obj, "file", None)
    if isinstance(legacy, str) and legacy.strip():
        storage = legacy.strip()
        return storage, _media_join(storage)
    if legacy is not None and hasattr(legacy, "name"):
        storage = getattr(legacy, "name", None) or None
        url = getattr(legacy, "url", None) or None
        if storage and url:
            return storage, url
        if storage:
            return storage, _media_join(storage)

    return None, None


def _get_active_entry(channel_slug: str):
    from .models import Channel, ChannelEntry

    ch = Channel.objects.filter(slug=channel_slug).first()
    if not ch:
        return None

    # Prefer is_active=True, lowest sort_order first
    qs = (
        ChannelEntry.objects.filter(channel=ch, is_active=True)
        .order_by("sort_order", "id")
    )
    return qs.first()


def _offset_seconds(entry) -> int:
    started = getattr(entry, "started_at", None)
    if not started:
        return 0
    try:
        return max(0, int((timezone.now() - started).total_seconds()))
    except Exception:
        return 0


@require_GET
def now_json(request, channel: Optional[str] = None):
    """
    Works for:
      /now.json
      /api/freestyle/channel/<slug>/now.json

    Returns:
      { ok, channel, offset_seconds, now:{id,title,storage_name,play_url,...} }
    """
    slug = _channel_slug(request, channel)

    try:
        entry = _get_active_entry(slug)
        if not entry:
            return JsonResponse(
                {
                    "ok": True,
                    "channel": slug,
                    "offset_seconds": 0,
                    "now": None,
                    "item": None,   # keep legacy key (some JS uses it)
                }
            )

        video = getattr(entry, "video", None)
        storage_name, play_url = _extract_storage_and_url(video)

        payload = {
            "ok": True,
            "channel": slug,
            "offset_seconds": _offset_seconds(entry),
            "now": {
                "id": getattr(video, "id", None),
                "title": getattr(video, "title", None),
                "duration_seconds": _safe_int(getattr(video, "duration_seconds", 0), 0),
                "is_hls": bool(getattr(video, "is_hls", False)),
                "storage_name": storage_name,
                "play_url": play_url,
                "entry_id": getattr(entry, "id", None),
            },
            "item": None,  # legacy key
        }
        return JsonResponse(payload)

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e), "channel": slug}, status=500)


@require_GET
def messages_json(request, channel: Optional[str] = None):
    slug = _channel_slug(request, channel)
    after_id = _safe_int(request.GET.get("after_id", 0), 0)

    # Keep it simple/compatible: your UI just needs "messages" list.
    try:
        from .models import ChatMessage
    except Exception:
        return JsonResponse({"ok": True, "messages": []})

    try:
        qs = ChatMessage.objects.all().order_by("id")
        if hasattr(ChatMessage, "channel_slug"):
            qs = qs.filter(channel_slug=slug)
        elif hasattr(ChatMessage, "channel"):
            qs = qs.filter(channel__slug=slug)

        if after_id:
            qs = qs.filter(id__gt=after_id)

        qs = qs[:50]
        out = []
        for m in qs:
            out.append(
                {
                    "id": getattr(m, "id", None),
                    "name": getattr(m, "name", None) or getattr(m, "user_name", None),
                    "text": getattr(m, "text", None) or getattr(m, "message", None),
                    "created_at": getattr(m, "created_at", None),
                }
            )
        return JsonResponse({"ok": True, "messages": out})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e), "messages": []}, status=500)


@require_GET
def ping_json(request, channel: Optional[str] = None):
    # Keep same shape you were already returning (so your JS doesn't break)
    slug = _channel_slug(request, channel)
    return JsonResponse(
        {
            "ok": True,
            "channel": slug,
            "server_time": timezone.now().isoformat(),
            "watching": None,
        }
    )
