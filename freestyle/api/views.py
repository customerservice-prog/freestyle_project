from __future__ import annotations

import json
from urllib.parse import urlparse

from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from freestyle.models import Channel, ChannelEntry, FreestyleVideo, ChatMessage, VideoReaction


def _json_ok(payload: dict, status: int = 200) -> JsonResponse:
    return JsonResponse({"ok": True, **payload}, status=status)


def _json_err(message: str, status: int = 400, **extra) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message, **extra}, status=status)


def _client_id(request) -> str:
    cid = request.COOKIES.get("freestyle_client_id") or request.headers.get("X-Client-Id")
    if cid:
        return str(cid)[:64]
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:120]
    ip = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    return f"{ip}:{ua}"[:64]


def _is_absolute_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return bool(p.scheme and p.netloc)
    except Exception:
        return False


def _resolve_play_url(request, video: FreestyleVideo) -> str:
    """
    Returns a URL that the browser can actually load.
    Priority:
      1) video.playback_url (if set)
      2) video.video_file.url (if file attached)
    Returns "" only if both are missing.
    """
    play_url = (getattr(video, "playback_url", "") or "").strip()

    # If playback_url exists but is relative, make absolute
    if play_url:
        if play_url.startswith("/"):
            return request.build_absolute_uri(play_url)
        if _is_absolute_url(play_url):
            return play_url
        # treat as relative path
        return request.build_absolute_uri("/" + play_url.lstrip("/"))

    # fallback to file field
    vf = getattr(video, "video_file", None)
    if vf:
        try:
            if vf.name:
                return request.build_absolute_uri(vf.url)
        except Exception:
            return ""

    return ""


@require_http_methods(["GET"])
def channel_now(request, channel_slug: str) -> JsonResponse:
    """
    Returns:
      { ok: true, item: { video_id, title, play_url, is_hls, duration_seconds, offset_seconds } }
    """
    channel = get_object_or_404(Channel, slug=channel_slug)

    entry = (
        ChannelEntry.objects.select_related("video")
        .filter(channel=channel, is_active=True, video__isnull=False)
        .order_by("position", "id")
        .first()
    )

    if not entry or not entry.video:
        return _json_ok({"item": None})

    video: FreestyleVideo = entry.video
    play_url = _resolve_play_url(request, video)

    # If this is blank, your admin record is missing BOTH playback_url and video_file
    if not play_url:
        return _json_err(
            "No playable URL for this video (playback_url empty AND video_file not attached).",
            status=500,
            debug={
                "video_id": video.id,
                "title": getattr(video, "title", ""),
                "playback_url": getattr(video, "playback_url", ""),
                "video_file_name": getattr(getattr(video, "video_file", None), "name", None),
            },
        )

    # mark played once if field exists
    if hasattr(entry, "has_played_once") and not entry.has_played_once:
        entry.has_played_once = True
        entry.save(update_fields=["has_played_once"])

    item = {
        "video_id": video.id,
        "title": video.title,
        "play_url": play_url,
        "is_hls": play_url.lower().endswith(".m3u8"),
        "duration_seconds": getattr(video, "duration_seconds", 0) or 0,
        "offset_seconds": 0,
    }
    return _json_ok({"item": item})


@require_http_methods(["GET"])
def chat_messages(request, channel_slug: str) -> JsonResponse:
    channel = get_object_or_404(Channel, slug=channel_slug)
    after_id = request.GET.get("after_id", "0")
    try:
        after_id_int = int(after_id)
    except ValueError:
        after_id_int = 0

    qs = ChatMessage.objects.filter(channel=channel, id__gt=after_id_int).order_by("id")[:200]
    messages = [
        {"id": m.id, "user": m.username, "message": m.message, "created_at": m.created_at.isoformat()}
        for m in qs
    ]
    return _json_ok({"messages": messages})


@csrf_exempt
@require_http_methods(["POST"])
def chat_send(request, channel_slug: str) -> JsonResponse:
    channel = get_object_or_404(Channel, slug=channel_slug)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    username = (body.get("user") or body.get("username") or "guest")[:32]
    message = (body.get("message") or "").strip()[:400]
    if not message:
        return _json_err("Message is empty", status=400)

    m = ChatMessage.objects.create(channel=channel, username=username, message=message, created_at=timezone.now())
    return _json_ok({"id": m.id})


@require_http_methods(["GET"])
def reactions_state(request, channel_slug: str) -> JsonResponse:
    channel = get_object_or_404(Channel, slug=channel_slug)
    video_id = request.GET.get("video_id")
    try:
        vid = int(video_id)
    except (TypeError, ValueError):
        return _json_err("Invalid video_id", status=400)

    qs = VideoReaction.objects.filter(channel=channel, video_id=vid)
    return _json_ok({"video_id": vid, "counts": {"fire": qs.filter(reaction="fire").count(), "nah": qs.filter(reaction="nah").count()}})


@csrf_exempt
@require_http_methods(["POST"])
def reactions_vote(request, channel_slug: str) -> JsonResponse:
    channel = get_object_or_404(Channel, slug=channel_slug)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    video_id = body.get("video_id")
    reaction = (body.get("reaction") or "").lower().strip()

    try:
        vid = int(video_id)
    except (TypeError, ValueError):
        return _json_err("Invalid video_id", status=400)

    if reaction not in ("fire", "nah"):
        return _json_err("reaction must be 'fire' or 'nah'", status=400)

    get_object_or_404(FreestyleVideo, id=vid)
    cid = _client_id(request)

    try:
        VideoReaction.objects.create(channel=channel, video_id=vid, client_id=cid, reaction=reaction)
        return _json_ok({"voted": True, "already_voted": False, "video_id": vid, "reaction": reaction})
    except IntegrityError:
        return _json_ok({"voted": False, "already_voted": True, "video_id": vid, "reaction": reaction})

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.shortcuts import get_object_or_404

@csrf_exempt
@require_http_methods(["POST"])
def channel_reset(request, channel_slug: str):
    channel = get_object_or_404(Channel, slug=channel_slug)
    channel.started_at = timezone.now()
    channel.save(update_fields=["started_at"])
    return JsonResponse({"ok": True, "reset": True})