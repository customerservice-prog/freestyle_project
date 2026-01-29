from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count

from freestyle.models import (
    Channel,
    ChannelEntry,
    FreestyleVideo,
    ChatMessage,
    ChatReaction,
)

# If live DB is empty, TV will still play this so it never goes black.
DEMO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
VERSION = "FREESTYLE-LIVEFINAL-CHAT-1"


def _active_channel_videos(channel_slug: str):
    try:
        channel = Channel.objects.get(slug=channel_slug)
    except Channel.DoesNotExist:
        return []

    entries = (
        ChannelEntry.objects
        .select_related("video")
        .filter(channel=channel, active=True, video__status="published")
        .order_by("position", "id")
    )
    return [e.video for e in entries if e.video]


def _pick_live_item(videos):
    if not videos:
        return None, 0

    durations = [max(1, int(v.duration_seconds or 1)) for v in videos]
    total = sum(durations) or 1

    now = int(timezone.now().timestamp())
    pos = now % total

    running = 0
    for v, d in zip(videos, durations):
        if running + d > pos:
            return v, int(pos - running)
        running += d

    return videos[0], 0


@require_GET
def api_now(request, channel: str):
    videos = _active_channel_videos(channel)

    # fallback: if no channel entries exist, try any published videos
    if not videos:
        videos = list(FreestyleVideo.objects.filter(status="published").order_by("-created_at", "-id"))

    video, offset = _pick_live_item(videos)

    # ALWAYS return something playable
    if video is None:
        return JsonResponse({
            "version": VERSION,
            "item": {"video_id": "demo", "play_url": DEMO_URL, "is_hls": False},
            "offset_seconds": 0,
            "error": "no_videos",
        })

    play_url = video.get_play_url() or DEMO_URL
    if play_url.startswith("/"):
        play_url = request.build_absolute_uri(play_url)

    return JsonResponse({
        "version": VERSION,
        "item": {
            "video_id": str(video.id),
            "play_url": play_url,
            "is_hls": bool(video.is_hls()),
        },
        "offset_seconds": int(offset),
    })


@require_GET
def api_captions(request, video_id: int):
    try:
        v = FreestyleVideo.objects.get(id=video_id)
    except FreestyleVideo.DoesNotExist:
        return JsonResponse({"words": []})

    words = v.captions_words or []
    if not isinstance(words, list):
        words = []
    return JsonResponse({"words": words})


# =========================
# CHAT (polling)
# =========================

@require_GET
def api_chat_latest(request, channel: str):
    after_id = int(request.GET.get("after_id") or 0)
    limit = min(200, max(1, int(request.GET.get("limit") or 60)))

    qs = ChatMessage.objects.filter(channel=channel, id__gt=after_id).order_by("id")[:limit]
    items = [{
        "id": m.id,
        "channel": m.channel,
        "video_id": m.video_id,
        "username": m.username,
        "message": m.message,
        "created_at": m.created_at.isoformat(),
    } for m in qs]

    return JsonResponse({"items": items})


@csrf_exempt
@require_POST
def api_chat_post(request, channel: str):
    username = (request.POST.get("username") or "").strip()
    message = (request.POST.get("message") or "").strip()
    video_id = (request.POST.get("video_id") or "").strip()

    if not username:
        username = "Guest"
    if not message:
        return JsonResponse({"ok": False, "error": "empty_message"}, status=400)

    username = username[:48]
    message = message[:280]
    video_id = video_id[:32]

    m = ChatMessage.objects.create(channel=channel, username=username, message=message, video_id=video_id)
    return JsonResponse({"ok": True, "id": m.id})


# =========================
# REACTIONS (one per user per video)
# =========================

@require_GET
def api_reaction_counts(request, channel: str, video_id: str):
    qs = (
        ChatReaction.objects
        .filter(channel=channel, video_id=str(video_id))
        .values("kind")
        .annotate(c=Count("id"))
    )
    counts = {"fire": 0, "nah": 0}
    for row in qs:
        k = row["kind"]
        if k in counts:
            counts[k] = int(row["c"])
    return JsonResponse({"video_id": str(video_id), "counts": counts})


@csrf_exempt
@require_POST
def api_reaction_vote(request, channel: str, video_id: str):
    kind = (request.POST.get("kind") or "").strip().lower()
    user_key = (request.POST.get("user_key") or "").strip()

    if kind not in ("fire", "nah"):
        return JsonResponse({"ok": False, "error": "bad_kind"}, status=400)
    if not user_key:
        return JsonResponse({"ok": False, "error": "missing_user_key"}, status=400)

    user_key = user_key[:64]
    video_id = str(video_id)[:32]

    ChatReaction.objects.get_or_create(
        channel=channel,
        video_id=video_id,
        user_key=user_key,
        defaults={"kind": kind},
    )

    return api_reaction_counts(request, channel, video_id)
