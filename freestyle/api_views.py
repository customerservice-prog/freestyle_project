import json
from urllib.parse import urlparse

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Channel, ChannelEntry, FreestyleVideo, ChatMessage, VideoReaction


def _is_hls(url: str) -> bool:
    try:
        path = urlparse(url).path.lower()
    except Exception:
        path = (url or "").lower()
    return path.endswith(".m3u8")


def _abs(request, maybe_url: str) -> str:
    if not maybe_url:
        return ""
    # already absolute
    if maybe_url.startswith("http://") or maybe_url.startswith("https://"):
        return maybe_url
    return request.build_absolute_uri(maybe_url)


def _get_or_create_channel(channel_slug: str) -> Channel:
    ch, _ = Channel.objects.get_or_create(
        slug=channel_slug,
        defaults={"name": channel_slug.capitalize(), "started_at": timezone.now()},
    )
    # if started_at missing somehow
    if not ch.started_at:
        ch.started_at = timezone.now()
        ch.save(update_fields=["started_at"])
    return ch


def _pick_scheduled_item(channel: Channel):
    """
    Build a loop schedule across active entries by duration_seconds.
    Returns: (entry, offset_seconds)
    """
    entries = list(
        ChannelEntry.objects.filter(channel=channel, is_active=True)
        .select_related("video")
        .order_by("position", "id")
    )

    # Auto-fill: if channel has no entries but videos exist, add latest video as entry
    if not entries:
        v = FreestyleVideo.objects.order_by("-id").first()
        if v:
            ChannelEntry.objects.create(channel=channel, video=v, position=0, is_active=True)
            entries = list(
                ChannelEntry.objects.filter(channel=channel, is_active=True)
                .select_related("video")
                .order_by("position", "id")
            )

    if not entries:
        return None, 0

    # durations: default 60 seconds if missing (prevents divide by zero)
    durations = []
    for e in entries:
        d = 60
        if e.video and e.video.duration_seconds and e.video.duration_seconds > 0:
            d = int(e.video.duration_seconds)
        durations.append(d)

    total = sum(durations) or 60

    elapsed = int((timezone.now() - channel.started_at).total_seconds())
    if elapsed < 0:
        elapsed = 0
    t = elapsed % total

    acc = 0
    for e, d in zip(entries, durations):
        if t < acc + d:
            return e, (t - acc)
        acc += d

    return entries[0], 0


@require_GET
def now_json(request, channel_slug: str):
    try:
        channel = _get_or_create_channel(channel_slug)
        entry, offset = _pick_scheduled_item(channel)

        # Always return valid JSON (never 500)
        if not entry or not entry.video:
            return JsonResponse(
                {"ok": True, "item": None, "offset_seconds": 0},
                status=200,
            )

        v = entry.video
        play_url = _abs(request, v.play_url())

        item = {
            "video_id": v.id,
            "title": v.title,
            "play_url": play_url,
            "is_hls": _is_hls(play_url),
            "duration_seconds": v.duration_seconds or 0,
        }
        return JsonResponse({"ok": True, "item": item, "offset_seconds": int(offset)}, status=200)

    except Exception as e:
        # final safety net: DO NOT 500 the frontend
        return JsonResponse({"ok": False, "error": str(e), "item": None, "offset_seconds": 0}, status=200)


@require_GET
def captions_json(request, video_id: int):
    v = FreestyleVideo.objects.filter(id=video_id).first()
    if not v:
        return JsonResponse({"ok": False, "words": []}, status=200)

    words = v.captions_words or []
    if not isinstance(words, list):
        words = []
    return JsonResponse({"ok": True, "words": words}, status=200)


@require_GET
def chat_messages_json(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)
    try:
        after_id = int(request.GET.get("after_id", "0") or "0")
    except Exception:
        after_id = 0

    qs = ChatMessage.objects.filter(channel=channel, id__gt=after_id).order_by("id")[:100]
    items = [
        {"id": m.id, "username": m.username, "message": m.message, "created_at": m.created_at.isoformat()}
        for m in qs
    ]
    return JsonResponse({"ok": True, "items": items}, status=200)


@csrf_exempt
@require_POST
def chat_send(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    username = (payload.get("username") or "anon")[:80]
    message = (payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"ok": False, "error": "empty message"}, status=200)

    # attach current playing video (optional)
    entry, _ = _pick_scheduled_item(channel)
    video = entry.video if entry and entry.video else None

    m = ChatMessage.objects.create(channel=channel, username=username, message=message[:1000], video=video)
    return JsonResponse({"ok": True, "id": m.id}, status=200)


@require_GET
def reactions_state_json(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)
    video_id = request.GET.get("video_id")
    if not video_id:
        return JsonResponse({"ok": True, "counts": {"fire": 0, "nah": 0}, "voted": False}, status=200)

    v = FreestyleVideo.objects.filter(id=video_id).first()
    if not v:
        return JsonResponse({"ok": True, "counts": {"fire": 0, "nah": 0}, "voted": False}, status=200)

    fire = VideoReaction.objects.filter(channel=channel, video=v, reaction="fire").count()
    nah = VideoReaction.objects.filter(channel=channel, video=v, reaction="nah").count()

    client_id = request.headers.get("X-Client-Id", "")[:64]
    voted = False
    if client_id:
        voted = VideoReaction.objects.filter(channel=channel, video=v, client_id=client_id).exists()

    return JsonResponse({"ok": True, "counts": {"fire": fire, "nah": nah}, "voted": voted}, status=200)


@csrf_exempt
@require_POST
def reactions_vote(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    video_id = payload.get("video_id")
    reaction = (payload.get("reaction") or "").strip().lower()
    client_id = (payload.get("client_id") or "").strip()[:64]

    if reaction not in ("fire", "nah"):
        return JsonResponse({"ok": False, "error": "invalid reaction"}, status=200)
    if not video_id or not client_id:
        return JsonResponse({"ok": False, "error": "missing video_id/client_id"}, status=200)

    v = FreestyleVideo.objects.filter(id=video_id).first()
    if not v:
        return JsonResponse({"ok": False, "error": "video not found"}, status=200)

    # UniqueConstraint prevents double votes; handle gracefully
    obj, created = VideoReaction.objects.get_or_create(
        channel=channel,
        video=v,
        client_id=client_id,
        defaults={"reaction": reaction},
    )
    if not created:
        return JsonResponse({"ok": True, "already_voted": True}, status=200)

    return JsonResponse({"ok": True, "created": True}, status=200)
