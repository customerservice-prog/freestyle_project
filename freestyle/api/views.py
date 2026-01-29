import json
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from freestyle.models import Channel, ChannelEntry, FreestyleVideo, ChatMessage, ChatReaction


def _client_id_from_request(request):
    cid = request.headers.get("X-Client-Id") or request.META.get("HTTP_X_CLIENT_ID") or ""
    return (cid or "").strip()[:80]


@require_GET
def channel_now_json(request, slug):
    """
    Returns:
    {
      "version": "FREESTYLE-LIVEFINAL-CHAT-1",
      "item": {"video_id": "...", "play_url":"...", "is_hls": false},
      "offset_seconds": 123
    }
    """
    channel = Channel.objects.filter(slug=slug).first()
    if not channel:
        channel = Channel.objects.create(slug=slug, name=slug.title())

    # Ensure channel has a started_at
    if channel.started_at is None:
        channel.started_at = timezone.now()
        channel.save(update_fields=["started_at"])

    entries = list(
        ChannelEntry.objects.select_related("video")
        .filter(channel=channel, active=True)
        .order_by("position", "id")
    )

    if not entries:
        return JsonResponse({"item": None, "offset_seconds": 0, "error": "no_videos"}, status=200)

    # total loop duration
    durations = []
    for e in entries:
        d = int(getattr(e.video, "duration_seconds", 30) or 30)
        durations.append(max(1, d))
    total = sum(durations) or 1

    elapsed = int((timezone.now() - channel.started_at).total_seconds())
    elapsed = max(0, elapsed)
    loop_pos = elapsed % total

    # find current entry
    acc = 0
    current = entries[0]
    current_dur = durations[0]
    offset = 0
    for e, dur in zip(entries, durations):
        if loop_pos < acc + dur:
            current = e
            current_dur = dur
            offset = loop_pos - acc
            break
        acc += dur

    v = current.video
    play_url = v.get_play_url()
    if not play_url:
        return JsonResponse({"item": None, "offset_seconds": 0, "error": "missing_play_url"}, status=200)

    # Keep admin stats (optional)
    if offset == 0 and not current.has_played_once:
        current.has_played_once = True
        current.play_count = (current.play_count or 0) + 1
        current.save(update_fields=["has_played_once", "play_count"])

    return JsonResponse({
        "version": "FREESTYLE-LIVEFINAL-CHAT-1",
        "item": {
            "video_id": str(v.id),
            "play_url": play_url,
            "is_hls": v.is_hls(),
        },
        "offset_seconds": int(offset),
    })


@require_GET
def video_captions_json(request, video_id):
    v = FreestyleVideo.objects.filter(id=video_id).first()
    if not v:
        return JsonResponse({"words": []})
    words = v.captions_words or []
    if not isinstance(words, list):
        words = []
    return JsonResponse({"words": words})


@require_GET
def chat_messages_json(request, slug):
    after_id = request.GET.get("after_id")
    try:
        after_id = int(after_id) if after_id else 0
    except Exception:
        after_id = 0

    qs = ChatMessage.objects.filter(channel=slug, id__gt=after_id).order_by("id")[:200]
    items = [{
        "id": m.id,
        "username": m.username,
        "message": m.message,
        "created_at": m.created_at.isoformat(),
    } for m in qs]

    return JsonResponse({"items": items})


@csrf_exempt
@require_POST
def chat_send(request, slug):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = request.POST

    username = (payload.get("username") or "Guest").strip()[:48]
    message = (payload.get("message") or "").strip()[:280]

    if not message:
        return JsonResponse({"ok": False, "error": "empty"}, status=400)

    m = ChatMessage.objects.create(channel=slug, username=username, message=message)
    return JsonResponse({
        "ok": True,
        "item": {"id": m.id, "username": m.username, "message": m.message, "created_at": m.created_at.isoformat()}
    })


@require_GET
def reaction_state_json(request, slug):
    video_id = (request.GET.get("video_id") or "").strip()
    if not video_id:
        return JsonResponse({"ok": False, "error": "missing_video_id"}, status=400)

    counts = (ChatReaction.objects
              .filter(channel=slug, video_id=video_id)
              .values("reaction")
              .annotate(c=Count("id")))

    out = {"fire": 0, "nah": 0}
    for row in counts:
        out[row["reaction"]] = row["c"]

    client_id = _client_id_from_request(request)
    voted = None
    if client_id:
        existing = ChatReaction.objects.filter(channel=slug, video_id=video_id, client_id=client_id).first()
        if existing:
            voted = existing.reaction

    return JsonResponse({"ok": True, "counts": out, "voted": voted})


@csrf_exempt
@require_POST
def reaction_vote(request, slug):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = request.POST

    video_id = (payload.get("video_id") or "").strip()
    reaction = (payload.get("reaction") or "").strip()

    if reaction not in ("fire", "nah"):
        return JsonResponse({"ok": False, "error": "bad_reaction"}, status=400)
    if not video_id:
        return JsonResponse({"ok": False, "error": "missing_video_id"}, status=400)

    client_id = (payload.get("client_id") or _client_id_from_request(request)).strip()[:80]
    if not client_id:
        return JsonResponse({"ok": False, "error": "missing_client_id"}, status=400)

    # Enforce one per video per client
    obj = ChatReaction.objects.filter(video_id=video_id, client_id=client_id).first()
    if obj:
        return JsonResponse({"ok": True, "already_voted": True, "voted": obj.reaction})

    ChatReaction.objects.create(channel=slug, video_id=video_id, client_id=client_id, reaction=reaction)
    return JsonResponse({"ok": True, "already_voted": False, "voted": reaction})
