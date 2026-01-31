# api/views.py
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count
from django.shortcuts import get_object_or_404

from freestyle.models import (
    Channel,
    ChannelEntry,
    FreestyleVideo,
    ChatMessage,
    VideoReaction,   # ✅ this replaces ChatReaction
)


def _json_ok(payload: dict, status: int = 200) -> JsonResponse:
    data = {"ok": True}
    data.update(payload)
    return JsonResponse(data, status=status)


def _json_err(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def _get_active_entry(channel: Channel) -> ChannelEntry | None:
    # Prefer an active entry, else fall back to first by position
    entry = (
        ChannelEntry.objects
        .filter(channel=channel, is_active=True)
        .select_related("video")
        .order_by("position")
        .first()
    )
    if entry:
        return entry

    return (
        ChannelEntry.objects
        .filter(channel=channel)
        .select_related("video")
        .order_by("position")
        .first()
    )


def _compute_offset_seconds(entry: ChannelEntry) -> int:
    """
    Computes an offset into the video so playback looks "live".
    If you have a start_time field, we use it. If not, return 0.
    """
    # Support several possible field names without crashing
    start_dt = None
    for field_name in ("start_time", "started_at", "started_on", "created_at"):
        if hasattr(entry, field_name):
            start_dt = getattr(entry, field_name)
            if start_dt:
                break

    if not start_dt:
        return 0

    now = timezone.now()
    delta = now - start_dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0

    # If duration is set, loop inside duration
    duration = getattr(entry.video, "duration_seconds", 0) or 0
    if duration > 0:
        seconds = seconds % duration

    return seconds


@require_GET
def channel_now(request, channel_slug: str):
    """
    GET /api/freestyle/channel/<slug>/now.json
    """
    channel = get_object_or_404(Channel, slug=channel_slug)
    entry = _get_active_entry(channel)

    if not entry or not entry.video:
        return _json_ok({"item": None})

    video: FreestyleVideo = entry.video

    item = {
        "video_id": video.id,
        "title": getattr(video, "title", f"Video {video.id}"),
        "play_url": getattr(video, "playback_url", "") or getattr(video, "video_url", "") or "",
        "is_hls": bool(getattr(video, "is_hls", False)),
        "duration_seconds": int(getattr(video, "duration_seconds", 0) or 0),
        "offset_seconds": _compute_offset_seconds(entry),
    }
    return _json_ok({"item": item})


@require_GET
def chat_messages(request, channel_slug: str):
    """
    GET /api/freestyle/channel/<slug>/chat/messages.json?after_id=0
    """
    channel = get_object_or_404(Channel, slug=channel_slug)
    after_id = request.GET.get("after_id", "0")
    try:
        after_id_int = int(after_id)
    except ValueError:
        after_id_int = 0

    qs = (
        ChatMessage.objects
        .filter(channel=channel, id__gt=after_id_int)
        .order_by("id")[:50]
    )

    messages = []
    for m in qs:
        messages.append({
            "id": m.id,
            "user": getattr(m, "user_name", None) or getattr(m, "username", None) or "Guest",
            "message": getattr(m, "message", "") or "",
            "created_at": getattr(m, "created_at", None).isoformat() if getattr(m, "created_at", None) else None,
        })

    return _json_ok({"messages": messages})


@csrf_exempt
@require_POST
def chat_post(request, channel_slug: str):
    """
    POST /api/freestyle/channel/<slug>/chat/post.json
    Body (form or json):
      - message
      - user (optional)
    """
    channel = get_object_or_404(Channel, slug=channel_slug)

    # Accept form-encoded or JSON
    message = request.POST.get("message", "").strip()
    user = request.POST.get("user", "").strip()

    if not message:
        try:
            import json
            body = json.loads(request.body.decode("utf-8") or "{}")
            message = str(body.get("message", "")).strip()
            user = str(body.get("user", "")).strip()
        except Exception:
            pass

    if not message:
        return _json_err("Missing message", status=400)

    ChatMessage.objects.create(
        channel=channel,
        message=message,
        **({"user_name": user} if user and hasattr(ChatMessage, "user_name") else {})
    )

    return _json_ok({"posted": True})


@require_GET
def reactions_state(request, channel_slug: str):
    """
    GET /api/freestyle/channel/<slug>/reactions/state.json?video_id=123
    Returns totals for Fire/Nah.
    """
    get_object_or_404(Channel, slug=channel_slug)

    video_id = request.GET.get("video_id", "")
    try:
        video_id_int = int(video_id)
    except ValueError:
        return _json_err("Invalid video_id", status=400)

    # Aggregate counts by reaction value
    rows = (
        VideoReaction.objects
        .filter(video_id=video_id_int)
        .values("reaction")
        .annotate(c=Count("id"))
    )

    counts = {"fire": 0, "nah": 0}
    for r in rows:
        key = (r.get("reaction") or "").lower()
        if key in counts:
            counts[key] = int(r["c"])

    return _json_ok({"video_id": video_id_int, "counts": counts})


@csrf_exempt
@require_POST
def reactions_vote(request, channel_slug: str):
    """
    POST /api/freestyle/channel/<slug>/reactions/vote.json
    Body (form or json):
      - video_id
      - reaction: "fire" or "nah"
    """
    get_object_or_404(Channel, slug=channel_slug)

    video_id = request.POST.get("video_id", "")
    reaction = request.POST.get("reaction", "")

    if not video_id or not reaction:
        try:
            import json
            body = json.loads(request.body.decode("utf-8") or "{}")
            video_id = body.get("video_id", video_id)
            reaction = body.get("reaction", reaction)
        except Exception:
            pass

    try:
        video_id_int = int(video_id)
    except ValueError:
        return _json_err("Invalid video_id", status=400)

    reaction = (reaction or "").lower().strip()
    if reaction not in ("fire", "nah"):
        return _json_err("reaction must be 'fire' or 'nah'", status=400)

    # Ensure video exists
    get_object_or_404(FreestyleVideo, id=video_id_int)

    VideoReaction.objects.create(
        video_id=video_id_int,
        reaction=reaction,
    )

    return _json_ok({"voted": True, "video_id": video_id_int, "reaction": reaction})
