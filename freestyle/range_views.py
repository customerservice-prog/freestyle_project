import mimetypes
import os
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET


CHUNK_SIZE = 8192


@require_GET
def stream_media(request, filename: str):
    """
    Streams a file from MEDIA_ROOT/freestyle_videos/ with HTTP Range support.
    This is REQUIRED for fast seeking (live offset) on MP4.
    """
    base_dir = Path(settings.MEDIA_ROOT) / "freestyle_videos"
    file_path = (base_dir / filename).resolve()

    # Prevent path traversal
    if not str(file_path).startswith(str(base_dir.resolve())):
        return HttpResponseNotFound("Not found")

    if not file_path.exists() or not file_path.is_file():
        return HttpResponseNotFound("Not found")

    file_size = file_path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(file_path))
    content_type = content_type or "application/octet-stream"

    range_header = request.headers.get("Range", "").strip()
    if not range_header:
        # Full response
        resp = HttpResponse(open(file_path, "rb"), content_type=content_type)
        resp["Content-Length"] = str(file_size)
        resp["Accept-Ranges"] = "bytes"
        return resp

    # Parse Range: bytes=start-end
    try:
        units, rng = range_header.split("=", 1)
        if units != "bytes":
            raise ValueError("Only bytes supported")

        start_str, end_str = rng.split("-", 1)
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1

        start = max(0, start)
        end = min(end, file_size - 1)
        if start > end:
            raise ValueError("Invalid range")
    except Exception:
        resp = HttpResponse(status=416)
        resp["Content-Range"] = f"bytes */{file_size}"
        return resp

    length = end - start + 1

    def file_iter(path, offset, length):
        with open(path, "rb") as f:
            f.seek(offset)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    resp = HttpResponse(
        file_iter(file_path, start, length),
        status=206,
        content_type=content_type,
    )
    resp["Content-Length"] = str(length)
    resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    resp["Accept-Ranges"] = "bytes"
    return resp
