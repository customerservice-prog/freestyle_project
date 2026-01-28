import os
import time
import re
import mimetypes

from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.urls import reverse

from freestyle.models import Channel, ChannelEntry, FreestyleVideo

DEMO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"


def _safe_duration(v: FreestyleVideo) -> int:
    # IMPORTANT: live schedule depends on this
    d = int(v.duration_seconds or 0)
    if d < 5:
        d = 30
    return d


def _video_to_item(v: FreestyleVideo):
    """
    ✅ KEY FIX:
    If it's a local uploaded file, DO NOT return /media/... directly.
    Return the ranged stream endpoint instead so seeking works (live TV won’t restart on refresh).
    """
    if v.playback_url:
        play_url = v.playback_url
    elif v.video_file:
        play_url = reverse("video_stream", args=[v.id])  # /api/freestyle/video/<id>/stream
    else:
        play_url = ""

    if not play_url:
        return None

    return {
        "video_id": str(v.id),
        "title": v.title,
        "play_url": play_url,
        "is_hls": (play_url.lower().endswith(".m3u8") or "m3u8" in play_url.lower()),
        "duration_seconds": _safe_duration(v),
    }


def _get_playlist_items(slug: str):
    channel, _ = Channel.objects.get_or_create(slug=slug, defaults={"name": slug})

    entries = (
        ChannelEntry.objects
        .filter(channel=channel, active=True, video__status="published")
        .select_related("video")
        .order_by("position", "id")
    )

    items = []
    if entries.exists():
        for e in entries:
            it = _video_to_item(e.video)
            if it:
                items.append(it)
    else:
        qs = FreestyleVideo.objects.filter(status="published").order_by("created_at", "id")
        for v in qs:
            it = _video_to_item(v)
            if it:
                items.append(it)

    if not items:
        items = [{
            "video_id": "demo",
            "title": "Demo",
            "play_url": DEMO_URL,
            "is_hls": False,
            "duration_seconds": 30,
        }]

    return channel, items


def channel_playlist_json(request, slug: str):
    channel, items = _get_playlist_items(slug)
    return JsonResponse({"channel": channel.slug, "count": len(items), "items": items})


def channel_now_json(request, slug: str):
    """
    ✅ Live TV:
    All devices see same video+time because server chooses based on a stable anchor.
    """
    channel, items = _get_playlist_items(slug)

    total = sum(int(i.get("duration_seconds") or 0) for i in items)
    if total <= 0:
        return JsonResponse({"item": items[0], "offset_seconds": 0})

    anchor = int(channel.created_at.timestamp())
    now = int(time.time())
    elapsed = (now - anchor) % total

    cum = 0
    chosen = items[0]
    offset = 0

    for it in items:
        dur = int(it.get("duration_seconds") or 30)
        if elapsed < cum + dur:
            chosen = it
            offset = max(0, elapsed - cum)
            break
        cum += dur

    return JsonResponse({"item": chosen, "offset_seconds": int(offset)})


# -----------------------------
# ✅ Range streaming (THE FIX)
# -----------------------------

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")

def _file_iterator(fileobj, length, chunk_size=1024 * 512):
    remaining = length
    while remaining > 0:
        chunk = fileobj.read(min(chunk_size, remaining))
        if not chunk:
            break
        remaining -= len(chunk)
        yield chunk

def video_stream(request, video_id: int):
    """
    Streams uploaded video with HTTP Range support (206 Partial Content).
    This is what makes live-TV seeking work, so refresh does NOT restart.
    """
    try:
        v = FreestyleVideo.objects.get(pk=video_id)
    except FreestyleVideo.DoesNotExist:
        return HttpResponse(status=404)

    if not v.video_file:
        return HttpResponse(status=404)

    try:
        path = v.video_file.path
    except Exception:
        return HttpResponse(status=404)

    if not os.path.exists(path):
        return HttpResponse(status=404)

    file_size = os.path.getsize(path)
    content_type, _ = mimetypes.guess_type(path)
    if not content_type:
        content_type = "video/mp4"

    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")
    if not range_header:
        # Full file
        with open(path, "rb") as f:
            resp = StreamingHttpResponse(_file_iterator(f, file_size), content_type=content_type)
            resp["Content-Length"] = str(file_size)
            resp["Accept-Ranges"] = "bytes"
            return resp

    m = _RANGE_RE.match(range_header.strip())
    if not m:
        return HttpResponse(status=416)

    start_str, end_str = m.groups()
    if start_str == "" and end_str == "":
        return HttpResponse(status=416)

    if start_str == "":
        # suffix range: bytes=-500
        suffix = int(end_str)
        start = max(0, file_size - suffix)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1

    if start >= file_size:
        return HttpResponse(status=416)

    end = min(end, file_size - 1)
    length = (end - start) + 1

    f = open(path, "rb")
    f.seek(start)

    resp = StreamingHttpResponse(_file_iterator(f, length), status=206, content_type=content_type)
    resp["Content-Length"] = str(length)
    resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    resp["Accept-Ranges"] = "bytes"
    return resp


def video_captions_json(request, video_id: int):
    try:
        v = FreestyleVideo.objects.get(pk=video_id)
    except FreestyleVideo.DoesNotExist:
        return JsonResponse({"video_id": video_id, "words": []})

    words = v.captions_words or []
    if not isinstance(words, list):
        words = []

    return JsonResponse({"video_id": v.id, "words": words})
