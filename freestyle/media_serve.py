# freestyle/media_serve.py
import os
import mimetypes
from wsgiref.util import FileWrapper

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound


def _file_response(path, start=0, end=None, status=200):
    file_size = os.path.getsize(path)
    if end is None or end >= file_size:
        end = file_size - 1

    length = (end - start) + 1
    content_type, _ = mimetypes.guess_type(path)
    content_type = content_type or "application/octet-stream"

    with open(path, "rb") as f:
        f.seek(start)
        wrapper = FileWrapper(f, blksize=8192)
        resp = HttpResponse(wrapper, status=status, content_type=content_type)
        resp["Accept-Ranges"] = "bytes"
        resp["Content-Length"] = str(length)
        if status == 206:
            resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        return resp


def media_serve(request, path):
    # Map /media/<path> -> MEDIA_ROOT/<path>
    full_path = os.path.join(str(settings.MEDIA_ROOT), path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return HttpResponseNotFound("Not Found")

    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")
    if not range_header:
        return _file_response(full_path, status=200)

    # Example: "bytes=0-"
    try:
        units, rng = range_header.split("=")
        if units.strip() != "bytes":
            return _file_response(full_path, status=200)

        start_s, end_s = (rng.split("-") + [""])[:2]
        file_size = os.path.getsize(full_path)

        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1

        if start >= file_size:
            return _file_response(full_path, status=200)

        return _file_response(full_path, start=start, end=end, status=206)
    except Exception:
        return _file_response(full_path, status=200)
