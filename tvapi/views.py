import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.db.models import Count
from freestyle.models import Channel, ChannelEntry, FreestyleVideo, ChatMessage


def _is_hls(url: str) -> bool:
    u = (url or "").lower()
    return u.endswith(".m3u8")


def _video_play_url(request, v: FreestyleVideo) -> str:
    if v.playback_url:
        return v.playback_url
    if v.video_file:
        # build absolute so it works on live domains
        return request.build_absolute_uri(v.video_file.url)
    return ""


def _get_or_create_channel(channel_slug: str) -> Channel:
    # Always ensure channel exists so now.json never 500s on fresh DB
    ch, _ = Channel.objects.get_or_create(
        slug=channel_slug,
        defaults={"name": channel_slug.title(), "started_at": timezone.now()},
    )
    return ch


def _active_entries(channel: Channel):
    return (
        ChannelEntry.objects
        .select_related("video")
        .filter(channel=channel, is_active=True, video__isnull=False)
        .order_by("position", "id")
    )


@require_GET
def now_json(request, channel_slug: str):
    try:
        channel = _get_or_create_channel(channel_slug)
        entries = list(_active_entries(channel))

        # If no entries/videos, return clean JSON (NOT 500)
        if not entries:
            return JsonResponse(
                {
                    "ok": True,
                    "channel": {"slug": channel.slug, "name": channel.name},
                    "item": None,
                    "offset_seconds": 0,
                    "reason": "no_active_entries",
                }
            )

        # Build playlist with durations (default 60 if missing)
        playlist = []
        for e in entries:
            dur = int(e.video.duration_seconds or 60)
            playlist.append((e.video, dur))

        total = sum(d for _, d in playlist) or 1

        elapsed = (timezone.now() - channel.started_at).total_seconds()
        elapsed = max(0, int(elapsed))
        t = elapsed % total

        current_video = playlist[0][0]
        offset = 0
        acc = 0
        for v, dur in playlist:
            if acc + dur > t:
                current_video = v
                offset = t - acc
                break
            acc += dur

        play_url = _video_play_url(request, current_video)

        # If a video exists but has no play url, still don't 500
        if not play_url:
            return JsonResponse(
                {
                    "ok": True,
                    "channel": {"slug": channel.slug, "name": channel.name},
                    "item": None,
                    "offset_seconds": 0,
                    "reason": "video_has_no_url",
                }
            )

        return JsonResponse(
            {
                "ok": True,
                "channel": {"slug": channel.slug, "name": channel.name},
                "item": {
                    "video_id": current_video.id,
                    "title": current_video.title,
                    "play_url": play_url,
                    "is_hls": _is_hls(play_url),
                    "duration_seconds": int(current_video.duration_seconds or 60),
                },
                "offset_seconds": int(offset),
                "server_time": timezone.now().isoformat(),
            }
        )
    except Exception as e:
        # Final safety: never leak 500s to the TV page
        return JsonResponse({"ok": False, "error": str(e)}, status=200)


@require_GET
def captions_json(request, video_id: int):
    # You can upgrade later; for now return empty words so frontend never breaks
    return JsonResponse({"ok": True, "video_id": video_id, "words": []})


@require_GET
def chat_messages_json(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)
    try:
        after_id = int(request.GET.get("after_id", "0"))
    except ValueError:
        after_id = 0

    qs = (
        ChatMessage.objects
        .filter(channel=channel, id__gt=after_id)
        .order_by("id")[:50]
    )

    items = []
    for m in qs:
        items.append(
            {
                "id": m.id,
                "username": m.username,
                "message": m.message,
                "created_at": m.created_at.isoformat(),
            }
        )

    return JsonResponse({"ok": True, "items": items})


@require_POST
def chat_send(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    username = (body.get("username") or "anon")[:80]
    message = (body.get("message") or "").strip()
    if not message:
        return JsonResponse({"ok": False, "error": "empty"}, status=200)

    ChatMessage.objects.create(channel=channel, username=username, message=message)
    return JsonResponse({"ok": True})


@require_GET
def reaction_state_json(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)
    video_id = request.GET.get("video_id")
    if not video_id:
        return JsonResponse({"ok": False, "error": "missing video_id"}, status=200)

    try:
        video = FreestyleVideo.objects.get(id=int(video_id))
    except Exception:
        return JsonResponse({"ok": False, "error": "bad video_id"}, status=200)

    counts = (
        VideoReaction.objects
        .filter(channel=channel, video=video)
        .values("reaction")
        .annotate(c=Count("id"))
    )

    out = {"fire": 0, "nah": 0}
    for row in counts:
        r = row["reaction"]
        if r in out:
            out[r] = row["c"]

    # optional “already voted” check (frontend also stores locally)
    client_id = request.headers.get("X-Client-Id", "") or request.GET.get("client_id", "")
    voted = False
    if client_id:
        voted = VideoReaction.objects.filter(channel=channel, video=video, client_id=client_id).exists()

    return JsonResponse({"ok": True, "counts": out, "voted": voted})


@require_POST
def reaction_vote(request, channel_slug: str):
    channel = _get_or_create_channel(channel_slug)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    video_id = body.get("video_id")
    reaction = (body.get("reaction") or "").strip().lower()
    client_id = (body.get("client_id") or "").strip()

    if not video_id or reaction not in ("fire", "nah") or not client_id:
        return JsonResponse({"ok": False, "error": "missing_fields"}, status=200)

    try:
        video = FreestyleVideo.objects.get(id=int(video_id))
    except Exception:
        return JsonResponse({"ok": False, "error": "bad_video_id"}, status=200)

    obj, created = VideoReaction.objects.get_or_create(
        channel=channel,
        video=video,
        client_id=client_id,
        defaults={"reaction": reaction},
    )

    if not created:
        return JsonResponse({"ok": True, "already_voted": True})

    return JsonResponse({"ok": True, "already_voted": False})
