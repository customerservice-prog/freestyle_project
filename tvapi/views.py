# tvapi/views.py
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from freestyle.models import Channel, ChannelEntry, FreestyleVideo, ChatMessage, VideoReaction


def _is_hls(url: str) -> bool:
    u = (url or "").lower()
    return ".m3u8" in u


def _get_channel(channel_slug: str) -> Channel:
    return Channel.objects.get(slug=channel_slug)


def _get_active_entries(channel: Channel):
    return list(
        ChannelEntry.objects.select_related("video")
        .filter(channel=channel, is_active=True, video__isnull=False)
        .order_by("position", "id")
    )


def _pick_current(entries, elapsed_seconds: int):
    """
    Loop through entries based on duration_seconds.
    If duration_seconds missing, assume 300s per clip.
    """
    if not entries:
        return None, 0

    durations = []
    total = 0
    for e in entries:
        d = e.video.duration_seconds or 300
        d = max(5, int(d))
        durations.append(d)
        total += d

    if total <= 0:
        return entries[0], 0

    t = elapsed_seconds % total
    acc = 0
    for e, d in zip(entries, durations):
        if acc + d > t:
            return e, int(t - acc)
        acc += d

    return entries[-1], 0


def channel_now_json(request, channel_slug):
    try:
        channel = _get_channel(channel_slug)
    except Channel.DoesNotExist:
        return JsonResponse({"ok": False, "error": "channel_not_found"}, status=404)

    entries = _get_active_entries(channel)
    if not entries:
        return JsonResponse({"ok": True, "item": None, "offset_seconds": 0})

    elapsed = int((timezone.now() - channel.started_at).total_seconds())
    entry, offset = _pick_current(entries, elapsed)

    if not entry or not entry.video:
        return JsonResponse({"ok": True, "item": None, "offset_seconds": 0})

    play_url = entry.video.best_play_url
    if not play_url:
        return JsonResponse({"ok": False, "error": "missing_play_url"}, status=500)

    payload = {
        "ok": True,
        "item": {
            "video_id": entry.video_id,
            "title": entry.video.title,
            "play_url": play_url,
            "is_hls": _is_hls(play_url),
        },
        "offset_seconds": offset,
    }
    return JsonResponse(payload)


def video_captions_json(request, video_id: int):
    # Your TV HTML expects: { words: [{w,s,e}, ...] }
    # If you don't have captions stored yet, return empty list.
    try:
        FreestyleVideo.objects.get(id=video_id)
    except FreestyleVideo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "video_not_found"}, status=404)

    return JsonResponse({"ok": True, "words": []})


def chat_messages_json(request, channel_slug):
    try:
        channel = _get_channel(channel_slug)
    except Channel.DoesNotExist:
        return JsonResponse({"ok": False, "error": "channel_not_found"}, status=404)

    after_id = int(request.GET.get("after_id", "0") or 0)
    qs = (
        ChatMessage.objects.filter(channel=channel, id__gt=after_id)
        .order_by("id")[:50]
    )

    items = []
    for m in qs:
        items.append({"id": m.id, "username": m.username, "message": m.message})

    return JsonResponse({"ok": True, "items": items})


@csrf_exempt
def chat_send(request, channel_slug):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        channel = _get_channel(channel_slug)
    except Channel.DoesNotExist:
        return JsonResponse({"ok": False, "error": "channel_not_found"}, status=404)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)

    username = (data.get("username") or "anon")[:80]
    message = (data.get("message") or "").strip()
    if not message:
        return JsonResponse({"ok": False, "error": "empty_message"}, status=400)

    ChatMessage.objects.create(channel=channel, username=username, message=message[:280])
    return JsonResponse({"ok": True})


def reactions_state(request, channel_slug):
    try:
        channel = _get_channel(channel_slug)
    except Channel.DoesNotExist:
        return JsonResponse({"ok": False, "error": "channel_not_found"}, status=404)

    video_id = request.GET.get("video_id")
    if not video_id:
        return JsonResponse({"ok": False, "error": "missing_video_id"}, status=400)

    try:
        video = FreestyleVideo.objects.get(id=int(video_id))
    except Exception:
        return JsonResponse({"ok": False, "error": "video_not_found"}, status=404)

    counts_qs = (
        VideoReaction.objects.filter(channel=channel, video=video)
        .values("reaction")
        .annotate(c=Count("id"))
    )
    counts = {"fire": 0, "nah": 0}
    for row in counts_qs:
        r = row["reaction"]
        if r in counts:
            counts[r] = row["c"]

    client_id = request.headers.get("X-Client-Id", "") or ""
    voted = False
    if client_id:
        voted = VideoReaction.objects.filter(video=video, client_id=client_id).exists()

    return JsonResponse({"ok": True, "counts": counts, "voted": voted})


@csrf_exempt
def reactions_vote(request, channel_slug):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        channel = _get_channel(channel_slug)
    except Channel.DoesNotExist:
        return JsonResponse({"ok": False, "error": "channel_not_found"}, status=404)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)

    video_id = data.get("video_id")
    reaction = (data.get("reaction") or "").strip().lower()
    client_id = (data.get("client_id") or "").strip()

    if not video_id or not client_id or reaction not in ("fire", "nah"):
        return JsonResponse({"ok": False, "error": "bad_request"}, status=400)

    try:
        video = FreestyleVideo.objects.get(id=int(video_id))
    except Exception:
        return JsonResponse({"ok": False, "error": "video_not_found"}, status=404)

    obj, created = VideoReaction.objects.get_or_create(
        channel=channel, video=video, client_id=client_id,
        defaults={"reaction": reaction},
    )
    if not created:
        return JsonResponse({"ok": False, "already_voted": True})

    return JsonResponse({"ok": True})
