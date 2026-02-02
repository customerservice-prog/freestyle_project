# freestyle/views.py
import json
import os
import uuid
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required

from .models import (
    Channel,
    ChannelEntry,
    ChatMessage,
    Presence,
    VideoReaction,
    SponsorAd,
    FreestyleVideo,
)


# -----------------------
# Pages
# -----------------------
@ensure_csrf_cookie
def tv_page(request):
    ch, _ = Channel.objects.get_or_create(
        slug="main", defaults={"name": "Main", "is_default": True}
    )
    # ensure station clock exists (prevents None issues)
    if not getattr(ch, "schedule_started_at", None):
        ch.schedule_started_at = timezone.now()
        ch.save(update_fields=["schedule_started_at"])

    ad = SponsorAd.objects.filter(is_active=True).order_by("-id").first()
    return render(request, "freestyle/tv.html", {"channel": ch, "sponsor_ad": ad})


def access_page(request):
    next_url = request.GET.get("next") or "/"
    if request.user.is_authenticated:
        return redirect(next_url)

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST_toggle" and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect(next_url)

    # normal POST
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect(next_url)

    return render(request, "freestyle/access.html", {"form": form, "next": next_url})


def submit_page(request):
    return render(request, "freestyle/submit.html")


@login_required
def creator_dashboard(request):
    published = FreestyleVideo.objects.filter(uploaded_by=request.user).order_by("-id")
    return render(request, "freestyle/creator_dashboard.html", {"published": published})


@login_required
def creator_upload(request):
    return render(request, "freestyle/creator_upload.html")


# -----------------------
# Presence / viewers
# -----------------------
def _active_viewers(channel: Channel) -> int:
    cutoff = timezone.now() - timedelta(seconds=20)
    return Presence.objects.filter(channel=channel, last_seen__gte=cutoff).count()


@require_http_methods(["GET"])
def presence_ping(request):
    channel_slug = request.GET.get("channel", "main")
    sid = request.GET.get("sid") or str(uuid.uuid4())
    ch, _ = Channel.objects.get_or_create(
        slug=channel_slug, defaults={"name": channel_slug.title()}
    )

    Presence.objects.update_or_create(
        channel=ch,
        sid=sid,
        defaults={"last_seen": timezone.now()},
    )

    return JsonResponse({
        "ok": True,
        "sid": sid,
        "viewers": _active_viewers(ch),
    })


# -----------------------
# Scheduling helpers
# -----------------------
def _media_exists(play_url: str) -> bool:
    """
    If play_url is /media/... verify it exists on disk.
    If it's http(s) or something else, we assume it's valid.
    """
    if not play_url:
        return False
    u = str(play_url)
    if not u.startswith(settings.MEDIA_URL):
        return True  # remote or non-media path

    rel = u[len(settings.MEDIA_URL):].lstrip("/")
    path = os.path.join(str(settings.MEDIA_ROOT), rel)
    return os.path.exists(path)


def _scheduled_now(channel: Channel):
    """
    True station scheduler:
      - uses Channel.schedule_started_at as the global station clock
      - cycles through active ChannelEntry items in order
      - returns (entry, offset_seconds) for MP4 rotation
      - returns (entry, 0) for live/HLS
    """
    # ensure station clock exists
    if not getattr(channel, "schedule_started_at", None):
        channel.schedule_started_at = timezone.now()
        channel.save(update_fields=["schedule_started_at"])

    entries = (
        ChannelEntry.objects.filter(channel=channel, is_active=True)
        .select_related("video")
        .order_by("sort_order", "id")
    )

    playlist = []
    total = 0

    for e in entries:
        v = e.video
        if not v:
            continue

        # if live/HLS: return immediately
        if getattr(e, "is_live", False) or getattr(v, "is_hls", False):
            # if play_url is missing or dead, skip it instead of killing the channel
            if not v.play_url or not _media_exists(v.play_url):
                continue
            return e, 0

        # must have a playable URL
        if not v.play_url or not _media_exists(v.play_url):
            continue

        dur = int(v.duration_seconds or 0)
        if dur <= 1:
            continue

        playlist.append((e, dur))
        total += dur

    if not playlist or total <= 1:
        return None, 0

    elapsed = int((timezone.now() - channel.schedule_started_at).total_seconds())
    pos = elapsed % total

    for e, dur in playlist:
        if pos < dur:
            return e, pos
        pos -= dur

    return playlist[0][0], 0


# -----------------------
# NOW endpoint
# -----------------------
@require_http_methods(["GET"])
def now_json(request, channel):
    ch = get_object_or_404(Channel, slug=channel)
    entry, offset = _scheduled_now(ch)
    viewers = 1100 + _active_viewers(ch)

    ad = SponsorAd.objects.filter(is_active=True).order_by("-id").first()
    sponsor_payload = None
    if ad:
        sponsor_payload = {
            "title": ad.title,
            "description": ad.description,
            "image_url": ad.image_url,
            "click_url": ad.click_url,
        }

    if not entry:
        return JsonResponse({
            "ok": True,
            "item": None,
            "offset_seconds": 0,
            "viewers": viewers,
            "sponsor": sponsor_payload,
        })

    v = entry.video
    return JsonResponse({
        "ok": True,
        "item": {
            "video_id": v.id,
            "title": v.title,
            "play_url": v.play_url,
            "is_hls": v.is_hls,
            "artwork_url": getattr(v, "artwork_url", None),
            "duration_seconds": v.duration_seconds,
        },
        "offset_seconds": int(offset or 0),
        "viewers": viewers,
        "sponsor": sponsor_payload,
    })


# -----------------------
# Duration repair endpoint
# -----------------------
@require_http_methods(["POST"])
def save_duration_seconds(request, video_id: int):
    v = get_object_or_404(FreestyleVideo, id=video_id)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    dur = int(float(payload.get("duration_seconds") or 0))
    if dur < 2:
        return JsonResponse({"ok": False, "error": "bad_duration"}, status=400)

    if (v.duration_seconds or 0) == 0 or abs((v.duration_seconds or 0) - dur) >= 2:
        v.duration_seconds = dur
        v.save(update_fields=["duration_seconds"])

    return JsonResponse({"ok": True, "duration_seconds": v.duration_seconds})


# -----------------------
# Chat
# -----------------------
@require_http_methods(["GET"])
def chat_messages(request, channel):
    ch = get_object_or_404(Channel, slug=channel)
    after_id = int(request.GET.get("after_id") or 0)
    msgs = ChatMessage.objects.filter(channel=ch, id__gt=after_id).order_by("id")[:60]
    items = [{
        "id": m.id,
        "username": m.username,
        "message": m.message,
        "created_at": m.created_at.isoformat()
    } for m in msgs]
    return JsonResponse({"ok": True, "items": items})


@require_http_methods(["POST"])
def chat_send(request, channel):
    ch = get_object_or_404(Channel, slug=channel)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    username = (payload.get("username") or "Guest").strip()[:60]
    message = (payload.get("message") or "").strip()[:280]
    if not message:
        return JsonResponse({"ok": False, "error": "empty"}, status=400)

    ChatMessage.objects.create(channel=ch, username=username, message=message)
    return JsonResponse({"ok": True})


# -----------------------
# Reactions
# -----------------------
@require_http_methods(["GET"])
def reaction_state(request, channel):
    ch = get_object_or_404(Channel, slug=channel)
    video_id = request.GET.get("video_id")
    client_id = request.headers.get("X-Client-Id") or ""

    if not video_id:
        return JsonResponse({"ok": False}, status=400)

    fire_count = VideoReaction.objects.filter(channel=ch, video_id=video_id, reaction="fire").count()
    nah_count = VideoReaction.objects.filter(channel=ch, video_id=video_id, reaction="nah").count()

    voted = False
    if client_id:
        voted = VideoReaction.objects.filter(channel=ch, video_id=video_id, client_id=client_id).exists()

    return JsonResponse({
        "ok": True,
        "counts": {"fire": fire_count, "nah": nah_count},
        "voted": voted,
    })


@require_http_methods(["POST"])
def reaction_vote(request, channel):
    ch = get_object_or_404(Channel, slug=channel)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    video_id = str(payload.get("video_id") or "").strip()
    reaction = str(payload.get("reaction") or "").strip()
    client_id = str(payload.get("client_id") or "").strip()

    if not (video_id and reaction in ("fire", "nah") and client_id):
        return JsonResponse({"ok": False, "error": "bad_request"}, status=400)

    _, created = VideoReaction.objects.get_or_create(
        channel=ch,
        video_id=video_id,
        client_id=client_id,
        defaults={"reaction": reaction},
    )
    if not created:
        return JsonResponse({"ok": False, "already_voted": True})

    return JsonResponse({"ok": True})
