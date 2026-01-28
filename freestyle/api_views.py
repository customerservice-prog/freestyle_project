from __future__ import annotations

import os
import time
import mimetypes
import re
from typing import List, Dict, Tuple

from django.http import JsonResponse, StreamingHttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET

from .models import Channel, ChannelEntry, FreestyleVideo

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)", re.I)


def _no_store(resp: JsonResponse) -> JsonResponse:
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    return resp


def _is_hls(url: str) -> bool:
    u = (url or "").lower()
    return u.endswith(".m3u8") or "m3u8" in u


def _absolute(request, url: str) -> str:
    if url and url.startswith("/"):
        return request.build_absolute_uri(url)
    return url


def _local_file_exists(v: FreestyleVideo) -> bool:
    if not getattr(v, "video_file", None):
        return False
    try:
        path = v.video_file.path
    except Exception:
        return False
    return bool(path) and os.path.exists(path)


def _get_play_url(request, v: FreestyleVideo) -> str:
    """
    Live TV rule:
    - If local file exists -> use our Range-enabled stream endpoint
    - Else fallback to playback_url (external)
    """
    if _local_file_exists(v):
        stream_path = reverse("freestyle_video_stream", args=[v.id])
        return request.build_absolute_uri(stream_path)

    url = getattr(v, "playback_url", "") or ""
    if url:
        return _absolute(request, url)

    return ""


def _playlist_for_channel(request, slug: str) -> Tuple[Channel, List[Dict]]:
    channel = get_object_or_404(Channel, slug=slug)

    entries = (
        ChannelEntry.objects
        .filter(channel=channel, active=True)
        .select_related("video")
        .order_by("position", "id")
    )

    items: List[Dict] = []
    for e in entries:
        v: FreestyleVideo = e.video
        play_url = _get_play_url(request, v)
        if not play_url:
            continue

        dur = int(getattr(v, "duration_seconds", 0) or 0)
        if dur <= 0:
            dur = 30

        items.append({
            "channel_id": channel.id,
            "entry_id": e.id,
            "video_id": v.id,
            "title": getattr(v, "title", ""),
            "duration_seconds": dur,
            "play_url": play_url,
            "is_hls": _is_hls(play_url),
        })

    return channel, items


def _compute_now(server_epoch: int, items: List[Dict]) -> Tuple[int, int, int]:
    total = sum(int(i["duration_seconds"]) for i in items) or 1
    pos = server_epoch % total

    running = 0
    for idx, it in enumerate(items):
        d = int(it["duration_seconds"])
        if running + d > pos:
            return idx, int(pos - running), total
        running += d

    return 0, 0, total


@require_GET
def channel_schedule(request, slug: str):
    channel, items = _playlist_for_channel(request, slug)
    return _no_store(JsonResponse({
        "channel": {"id": channel.id, "slug": channel.slug, "name": getattr(channel, "name", channel.slug)},
        "count": len(items),
        "items": items,
    }))


@require_GET
def channel_now(request, slug: str):
    channel, items = _playlist_for_channel(request, slug)

    if not items:
        return _no_store(JsonResponse({
            "channel": {"id": channel.id, "slug": channel.slug},
            "error": "No playable videos in channel (missing files/urls).",
            "count": 0,
            "index": 0,
            "offset_seconds": 0,
            "item": None,
        }))

    server_epoch = int(time.time())
    idx, offset, total = _compute_now(server_epoch, items)

    return _no_store(JsonResponse({
        "channel": {"id": channel.id, "slug": channel.slug},
        "server_epoch": server_epoch,
        "cycle_total_seconds": total,
        "count": len(items),
        "index": idx,
        "offset_seconds": offset,
        "item": items[idx],
    }))


# -------------------------------
# Captions JSON
# -------------------------------
@require_GET
def video_captions(request, video_id: int):
    v = get_object_or_404(FreestyleVideo, id=video_id)
    words = getattr(v, "captions_words", None) or []
    # Expect list of {"w": "...", "s": float, "e": float}
    return _no_store(JsonResponse({
        "video_id": v.id,
        "count": len(words),
        "words": words,
    }))


# -------------------------------
# Range-enabled MP4 streaming
# -------------------------------
def _iter_file(path: str, start: int, end: int, chunk_size: int = 1024 * 512):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            yield chunk
            remaining -= len(chunk)


@require_GET
def video_stream(request, video_id: int):
    v = get_object_or_404(FreestyleVideo, id=video_id)

    if not _local_file_exists(v):
        raise Http404("Local file missing for this video")

    path = v.video_file.path
    file_size = os.path.getsize(path)

    content_type, _ = mimetypes.guess_type(path)
    content_type = content_type or "application/octet-stream"

    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")
    if range_header:
        m = RANGE_RE.match(range_header.strip())
        if m:
            start_s, end_s = m.groups()
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
        else:
            start, end = 0, file_size - 1

        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))

        resp = StreamingHttpResponse(_iter_file(path, start, end), status=206, content_type=content_type)
        resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        resp["Accept-Ranges"] = "bytes"
        resp["Content-Length"] = str(end - start + 1)
        resp["Cache-Control"] = "no-store"
        resp["Pragma"] = "no-cache"
        return resp

    resp = StreamingHttpResponse(_iter_file(path, 0, file_size - 1), content_type=content_type)
    resp["Accept-Ranges"] = "bytes"
    resp["Content-Length"] = str(file_size)
    resp["Cache-Control"] = "no-store"
    resp["Pragma"] = "no-cache"
    return resp
