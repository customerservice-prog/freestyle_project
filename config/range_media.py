from __future__ import annotations

import mimetypes
import os
import re
from pathlib import Path
from typing import Iterator

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET


_CHUNK_SIZE = 8192
_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _iter_file(path: Path, start: int, length: int) -> Iterator[bytes]:
    with path.open("rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@require_GET
def media_serve(request, path: str):
    """
    Range-enabled MEDIA serving for local dev.
    This prevents MP4 "restart every few seconds" when the player seeks to offset_seconds.
    """
    media_root = Path(settings.MEDIA_ROOT)
    full_path = (media_root / path).resolve()

    # Prevent path traversal
    if not str(full_path).startswith(str(media_root.resolve())):
        raise Http404("Invalid path")

    if not full_path.exists() or not full_path.is_file():
        raise Http404("Not found")

    size = full_path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(full_path))
    content_type = content_type or "application/octet-stream"

    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")

    # No Range => normal response (but still advertise Accept-Ranges)
    if not range_header:
        resp = FileResponse(full_path.open("rb"), content_type=content_type)
        resp["Content-Length"] = str(size)
        resp["Accept-Ranges"] = "bytes"
        return resp

    m = _RANGE_RE.match(range_header.strip())
    if not m:
        # Bad range => return full
        resp = FileResponse(full_path.open("rb"), content_type=content_type)
        resp["Content-Length"] = str(size)
        resp["Accept-Ranges"] = "bytes"
        return resp

    start_s, end_s = m.groups()

    # Parse start/end
    if start_s == "" and end_s == "":
        return HttpResponse(status=416)

    if start_s == "":
        # bytes=-500  (last 500 bytes)
        end = size - 1
        length = int(end_s)
        start = max(0, size - length)
    else:
        start = int(start_s)
        end = int(end_s) if end_s else size - 1

    # Clamp
    start = max(0, min(start, size - 1))
    end = max(start, min(end, size - 1))
    length = (end - start) + 1

    resp = StreamingHttpResponse(
        _iter_file(full_path, start, length),
        status=206,
        content_type=content_type,
    )
    resp["Content-Length"] = str(length)
    resp["Content-Range"] = f"bytes {start}-{end}/{size}"
    resp["Accept-Ranges"] = "bytes"
    return resp
