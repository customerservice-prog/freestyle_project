import os
import mimetypes
from wsgiref.util import FileWrapper

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse, Http404
from django.utils._os import safe_join


def stream_media_range(request, path):
    """
    Serve files from MEDIA_ROOT with HTTP Range support.
    This prevents MP4 freezing/stalling when we seek to offset_seconds.
    """
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
    except Exception:
        raise Http404("Invalid path")

    if not os.path.isfile(full_path):
        raise Http404("File not found")

    file_size = os.path.getsize(full_path)
    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or "video/mp4"

    range_header = request.META.get("HTTP_RANGE", "")
    if not range_header:
        resp = StreamingHttpResponse(FileWrapper(open(full_path, "rb")), content_type=content_type)
        resp["Content-Length"] = str(file_size)
        resp["Accept-Ranges"] = "bytes"
        return resp

    # Range: bytes=start-end
    try:
        units, rng = range_header.split("=", 1)
        if units.strip() != "bytes":
            return HttpResponse(status=416)

        start_str, end_str = rng.split("-", 1)
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1

        start = max(0, start)
        end = min(end, file_size - 1)
        if start > end:
            return HttpResponse(status=416)
    except Exception:
        return HttpResponse(status=416)

    length = end - start + 1
    fh = open(full_path, "rb")
    fh.seek(start)

    resp = StreamingHttpResponse(FileWrapper(fh), status=206, content_type=content_type)
    resp["Content-Length"] = str(length)
    resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    resp["Accept-Ranges"] = "bytes"
    return resp
