import os
import mimetypes
from pathlib import Path
from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, Http404

CHUNK = 8192

def stream_file(request, file_path: str):
    # file_path like "freestyle_videos/whatever.mp4"
    abs_path = Path(settings.MEDIA_ROOT) / file_path
    if not abs_path.exists() or not abs_path.is_file():
        raise Http404("File not found")

    file_size = abs_path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(abs_path))
    content_type = content_type or "application/octet-stream"

    range_header = request.headers.get("Range", "")
    if not range_header:
        resp = StreamingHttpResponse(open(abs_path, "rb"), content_type=content_type)
        resp["Content-Length"] = str(file_size)
        resp["Accept-Ranges"] = "bytes"
        return resp

    # Parse: "bytes=start-end"
    try:
        units, rng = range_header.split("=", 1)
        if units.strip() != "bytes":
            raise ValueError
        start_s, end_s = rng.split("-", 1)
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
        start = max(0, start)
        end = min(file_size - 1, end)
        if start > end:
            raise ValueError
    except Exception:
        return HttpResponse(status=416)

    length = end - start + 1

    def gen():
        with open(abs_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    resp = StreamingHttpResponse(gen(), status=206, content_type=content_type)
    resp["Content-Length"] = str(length)
    resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    resp["Accept-Ranges"] = "bytes"
    return resp
