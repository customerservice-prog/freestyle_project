# freestyle/tv_api_views.py
from __future__ import annotations

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Channel, ChannelEntry, FreestyleVideo, ChatMessage


def _best_media_url(video: FreestyleVideo) -> str:
    """
    IMPORTANT: This is the Step 3 fix.

    Your DB has: FreestyleVideo.video_file = "freestyle_videos/xyz.mp4"
    but older code often used: FreestyleVideo.file

    We always prefer video.video_file if present, and fall back to video.file.
    Returns "" if neither exists.
    """
    # Prefer new field
    vf = getattr(video, "video_file", None)
    if vf is not None:
        name = getattr(vf, "name", "") or ""
        if name:
            try:
                return vf.url
            except Exception:
                pass

    # Fallback legacy field (if your model still has it)
    f = getattr(video, "file", None)
    if f is not None:
        name = getattr(f, "name", "") or ""
        if name:
            try:
                return f.url
            except Exception:
                pass

    return ""


def _get_channel(slug: str | None):
    slug = (slug or "main").strip() or "main"
    return Channel.objects.filter(slug=slug).first()


def _current_entry(channel: Channel):
    """
    Pick the first active entry by sort_order/id.
    If you want rotation, we can add it later — this keeps it stable.
    """
    return (
        ChannelEntry.objects.filter(channel=channel, is_active=True)
        .select_related("video")
        .order_by("sort_order", "id")
        .first()
    )


@require_GET
def now_json(request):
    """
    Frontend calls /now.json to figure out what to play.
    We return the URL using video_file first (Step 3 fix).
    """
    slug = request.GET.get("channel") or request.headers.get("X-Channel") or "main"
    channel = _get_channel(slug)

    if not channel:
        return JsonResponse(
            {
                "ok": False,
                "error": "channel_not_found",
                "channel": slug,
                "play_url": "",
                "video_url": "",
            },
            status=200,
        )

    entry = _current_entry(channel)
    if not entry or not entry.video_id:
        return JsonResponse(
            {
                "ok": True,
                "channel": channel.slug,
                "is_live": False,
                "video": None,
                "play_url": "",
                "video_url": "",
                "src": "",
            },
            status=200,
        )

    video = entry.video
    url = _best_media_url(video)

    # Return MANY key names so your existing JS works no matter what it expects
    payload = {
        "ok": True,
        "channel": channel.slug,
        "is_live": bool(getattr(entry, "is_live", False)),
        "entry_id": entry.id,
        "video_id": video.id,

        # Common fields
        "title": getattr(video, "title", "") or "",
        "duration_seconds": getattr(video, "duration_seconds", None),

        # The important part (Step 3):
        "play_url": url,
        "video_url": url,
        "url": url,
        "src": url,

        # If your frontend expects nested objects:
        "video": {
            "id": video.id,
            "title": getattr(video, "title", "") or "",
            "duration_seconds": getattr(video, "duration_seconds", None),
            "play_url": url,
            "video_url": url,
            "url": url,
            "src": url,
            "is_hls": bool(getattr(video, "is_hls", False)),
        },
        "server_time": timezone.now().isoformat(),
    }

    return JsonResponse(payload, status=200)


@require_GET
def messages_json(request):
    """
    Your network tab shows: messages.json?after_id=0
    Return chat messages after an ID.
    """
    try:
        after_id = int(request.GET.get("after_id", "0") or "0")
    except ValueError:
        after_id = 0

    qs = ChatMessage.objects.all().order_by("id")
    if after_id > 0:
        qs = qs.filter(id__gt=after_id)

    # keep it light
    qs = qs.select_related(None)[:50]

    data = []
    for m in qs:
        data.append(
            {
                "id": m.id,
                "name": getattr(m, "name", "") or getattr(m, "user_name", "") or "anon",
                "message": getattr(m, "message", "") or getattr(m, "text", "") or "",
                "created_at": getattr(m, "created_at", None).isoformat() if getattr(m, "created_at", None) else None,
            }
        )

    return JsonResponse({"ok": True, "messages": data}, status=200)


@require_GET
def ping_json(request):
    """
    Your network tab shows ping.json?sid=...
    Keep it simple and always return ok.
    """
    return JsonResponse({"ok": True}, status=200)
