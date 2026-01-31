import json
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache

# Keep viewers alive if they ping within this many seconds
TTL_SECONDS = 30
CACHE_KEY = "freestyle_viewers_map_v1"


def _load_map():
    data = cache.get(CACHE_KEY) or {}
    # data: { viewer_id: last_seen_epoch }
    return data


def _save_map(m):
    cache.set(CACHE_KEY, m, timeout=TTL_SECONDS * 3)


def _prune(m):
    now = time.time()
    dead = [k for k, t in m.items() if (now - float(t)) > TTL_SECONDS]
    for k in dead:
        m.pop(k, None)
    return m


@csrf_exempt
def viewers_ping_json(request):
    """
    POST { viewer_id: "..." }
    """
    if request.method not in ("POST", "GET"):
        return JsonResponse({"ok": False, "error": "method_not_allowed"}, status=405)

    viewer_id = None

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            viewer_id = payload.get("viewer_id")
        except Exception:
            viewer_id = None
    else:
        viewer_id = request.GET.get("viewer_id")

    if not viewer_id:
        return JsonResponse({"ok": False, "error": "missing_viewer_id"}, status=400)

    m = _load_map()
    m = _prune(m)
    m[str(viewer_id)] = time.time()
    _save_map(m)

    return JsonResponse({"ok": True})


def viewers_count_json(request):
    m = _load_map()
    m = _prune(m)
    _save_map(m)
    return JsonResponse({"ok": True, "count": len(m)})
