import os
import time
import mimetypes
from wsgiref.util import FileWrapper

from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse, Http404
from django.db.models import Max

from .models import Channel, ChannelEntry

# Very simple in-memory presence map for dev.
# For production, move to Redis.
PRESENCE = {}  # (channel_slug, sid) -> last_seen_epoch


def _get_channel(channel_slug: str) -> Channel:
    ch, _ = Channel.objects.get_or_create(slug=channel_slug, defaults={"name": channel_slug.title()})
    if not ch.schedule_epoch:
        ch.schedule_epoch = int(time.time())
        ch.save(update_fields=["schedule_epoch"])
    return ch


def _playlist_for_channel(ch: Channel):
    entries = (
        ChannelEntry.objects
        .filter(channel=ch)
        .select_related("video")
        .order_by("position")
    )
    return list(entries)


def _pick_current(entries, schedule_epoch: int, now_epoch: int):
    """
    Map global time into playlist using duration_seconds (server side).
    Client does NOT rely on duration; it just plays the URL + offset.
    """
    if not entries:
        return None, schedule_epoch, 0

    durations = []
    total = 0
    for e in entries:
        d = int(e.video.duration_seconds or 0)
        if d <= 0:
            d = 1
        durations.append((e.video, d))
        total += d

    elapsed = max(0, int(now_epoch) - int(schedule_epoch))
    if total <= 0:
        v, _d = durations[0]
        return v, schedule_epoch, 0

    pos = elapsed % total

    running = 0
    for v, d in durations:
        if pos < running + d:
            offset = pos - running
            start_epoch = now_epoch - offset
            return v, int(start_epoch), int(offset)
        running += d

    v, _d = durations[0]
    return v, schedule_epoch, 0


def _count_viewers(channel_slug: str, now_epoch: int, ttl=45):
    dead = []
    for (ch, sid), last_seen in PRESENCE.items():
        if ch == channel_slug and (now_epoch - last_seen) <= ttl:
            continue
        if (now_epoch - last_seen) > ttl:
            dead.append((ch, sid))
    for k in dead:
        PRESENCE.pop(k, None)

    return sum(
        1 for (ch, _sid), last_seen in PRESENCE.items()
        if ch == channel_slug and (now_epoch - last_seen) <= ttl
    )


def presence_ping_json(request):
    sid = request.GET.get("sid", "").strip()
    channel_slug = request.GET.get("channel", "main").strip()
    now_epoch = int(time.time())

    if sid:
        PRESENCE[(channel_slug, sid)] = now_epoch

    return JsonResponse({"ok": True, "ts": now_epoch})


def now_json(request, channel):
    channel_slug = channel
    now_epoch = int(time.time())
    ch = _get_channel(channel_slug)
    entries = _playlist_for_channel(ch)

    video, start_epoch, offset_seconds = _pick_current(entries, ch.schedule_epoch, now_epoch)

    if not video:
        return JsonResponse({
            "ok": True,
            "channel": channel_slug,
            "title": "",
            "play_url": None,
            "captions_vtt": None,
            "duration_seconds": 0,
            "start_epoch": ch.schedule_epoch,
            "server_epoch": now_epoch,
            "offset_seconds": 0,
            "viewers": _count_viewers(channel_slug, now_epoch),
        })

    # IMPORTANT: Use /api/freestyle/stream/... instead of /media/... for smooth Range playback
    # video.file.name is like "freestyle_videos/filename.mp4"
    relpath = video.file.name.replace("\\", "/")
    play_url = request.build_absolute_uri(f"/api/freestyle/stream/{relpath}")

    return JsonResponse({
        "ok": True,
        "channel": channel_slug,
        "title": video.title,
        "play_url": play_url,
        "captions_vtt": request.build_absolute_uri(video.captions_vtt.url) if getattr(video, "captions_vtt", None) else None,
        "duration_seconds": int(video.duration_seconds or 0),
        "start_epoch": int(start_epoch),
        "server_epoch": int(now_epoch),
        "offset_seconds": int(offset_seconds),
        "viewers": _count_viewers(channel_slug, now_epoch),
    })


# -----------------------------
# STREAMING (Range/206) FOR MP4
# -----------------------------
def stream_media(request, relpath: str):
    """
    Streams a file from MEDIA_ROOT with HTTP Range support.
    This is REQUIRED for stable MP4 seeking/buffering in most browsers.
    URL: /api/freestyle/stream/<path>
    """
    relpath = (relpath or "").replace("\\", "/").lstrip("/")
    abs_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, relpath))

    media_root = os.path.abspath(settings.MEDIA_ROOT)
    if not abs_path.startswith(media_root):
        raise Http404("Invalid path")

    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        raise Http404("File not found")

    file_size = os.path.getsize(abs_path)
    content_type, _ = mimetypes.guess_type(abs_path)
    if not content_type:
        content_type = "application/octet-stream"

    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")
    if not range_header:
        # no Range -> normal streaming response
        resp = StreamingHttpResponse(FileWrapper(open(abs_path, "rb")), content_type=content_type)
        resp["Content-Length"] = str(file_size)
        resp["Accept-Ranges"] = "bytes"
        return resp

    # Parse Range: bytes=start-end
    try:
        units, rng = range_header.split("=", 1)
        if units.strip() != "bytes":
            return HttpResponse(status=416)

        start_str, end_str = rng.split("-", 1)
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1

        if start >= file_size:
            return HttpResponse(status=416)

        end = min(end, file_size - 1)
        length = end - start + 1
    except Exception:
        return HttpResponse(status=416)

    f = open(abs_path, "rb")
    f.seek(start)

    def iterator(fileobj, chunk_size=1024 * 512):
        remaining = length
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = fileobj.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data

    resp = StreamingHttpResponse(iterator(f), status=206, content_type=content_type)
    resp["Content-Length"] = str(length)
    resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    resp["Accept-Ranges"] = "bytes"
    return resp
