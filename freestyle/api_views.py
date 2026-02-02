from __future__ import annotations

import time
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.core.cache import cache


def _now_epoch() -> int:
    return int(time.time())


@require_GET
def now_json(request, channel: str):
    """
    JS expects:
      { ok, viewers, play_url, title, start_epoch, offset_seconds }
    This is written to be resilient to different model field names.
    """
    # --- viewers: count active sids in last 30s (set by ping) ---
    viewers_key = f"freestyle:viewers:{channel}"
    viewers_map = cache.get(viewers_key, {}) or {}
    now_ts = _now_epoch()
    # keep only last 30s
    viewers_map = {sid: ts for sid, ts in viewers_map.items() if now_ts - int(ts) <= 30}
    cache.set(viewers_key, viewers_map, timeout=60)
    viewers = max(1, len(viewers_map))

    # --- find "what's playing now" from your DB if models exist ---
    play_url = ""
    title = ""
    start_epoch = now_ts  # default
    try:
        from .models import ChannelEntry  # type: ignore

        qs = ChannelEntry.objects.all()

        # channel field might be string or FK; try common patterns safely
        if hasattr(ChannelEntry, "channel"):
            qs = qs.filter(channel=channel)

        entry = qs.order_by("-id").first()

        if entry:
            # start_epoch might be stored directly, or as datetime
            se = getattr(entry, "start_epoch", None)
            if isinstance(se, (int, float)) and se:
                start_epoch = int(se)
            else:
                start_dt = getattr(entry, "start_at", None) or getattr(entry, "started_at", None)
                if start_dt:
                    start_epoch = int(start_dt.timestamp())

            # title might be on entry or related video
            title = getattr(entry, "title", "") or ""

            video_obj = getattr(entry, "video", None) or getattr(entry, "freestylevideo", None)
            if video_obj:
                title = title or getattr(video_obj, "title", "") or ""
                # file/url fields vary; try common names
                f = (
                    getattr(video_obj, "file", None)
                    or getattr(video_obj, "video_file", None)
                    or getattr(video_obj, "src", None)
                    or getattr(video_obj, "url", None)
                )
                if f:
                    try:
                        # FileField
                        play_url = f.url
                    except Exception:
                        play_url = str(f)
            else:
                # sometimes entry stores url directly
                play_url = (
                    getattr(entry, "play_url", None)
                    or getattr(entry, "url", None)
                    or getattr(entry, "src", None)
                    or ""
                )

    except Exception:
        # If models aren't ready or fields differ, still respond OK
        pass

    offset_seconds = max(0, now_ts - int(start_epoch))

    return JsonResponse(
        {
            "ok": True,
            "channel": channel,
            "viewers": viewers,
            "play_url": play_url,
            "title": title,
            "start_epoch": int(start_epoch),
            "offset_seconds": int(offset_seconds),
        }
    )


@require_GET
def presence_ping(request):
    sid = (request.GET.get("sid") or "").strip()
    channel = (request.GET.get("channel") or "main").strip()

    if not sid:
        return JsonResponse({"ok": False, "error": "missing sid"}, status=400)

    viewers_key = f"freestyle:viewers:{channel}"
    viewers_map = cache.get(viewers_key, {}) or {}
    viewers_map[sid] = _now_epoch()
    cache.set(viewers_key, viewers_map, timeout=60)

    return JsonResponse({"ok": True})
