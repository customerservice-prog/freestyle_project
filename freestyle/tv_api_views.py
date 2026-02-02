# freestyle/tv_api_views.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple

from django.http import JsonResponse, HttpRequest
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Channel, ChannelEntry, ChatMessage, Presence, SponsorAd


# -------------------------
# Helpers
# -------------------------
def _get_channel_slug(request: HttpRequest, channel: Optional[str] = None) -> str:
    """
    Figure out which channel to use.
    Supports:
      - URL kwarg: /api/freestyle/channel/<slug>/now.json
      - querystring: ?channel=main
    Defaults to "main".
    """
    slug = (channel or "").strip().lower()
    if not slug:
        slug = (request.GET.get("channel") or request.GET.get("c") or "main").strip().lower()
    return slug or "main"


def _active_entries_for_channel(channel_obj: Channel) -> List[ChannelEntry]:
    # Order matches ChannelEntry.Meta ordering: sort_order, id
    return list(
        ChannelEntry.objects.select_related("video")
        .filter(channel=channel_obj, is_active=True)
        .order_by("sort_order", "id")
    )


def _video_payload(video) -> dict:
    """
    Return a payload the TV page can use.
    We include both:
      - play_url (what the player should load)
      - storage_name (path-ish, useful for debugging)
    """
    play_url = ""
    storage_name = ""

    # Prefer stored play_url if present (your model populates it on save)
    if getattr(video, "play_url", ""):
        play_url = video.play_url or ""

    # If video_file exists, use its .name as storage_name
    vf = getattr(video, "video_file", None)
    if vf is not None:
        try:
            storage_name = vf.name or ""
        except Exception:
            storage_name = ""

        # If play_url missing but file exists, fall back to .url
        if not play_url:
            try:
                play_url = vf.url
            except Exception:
                play_url = ""

    return {
        "id": video.id,
        "title": getattr(video, "title", "") or "",
        "duration_seconds": int(getattr(video, "duration_seconds", 0) or 0),
        "is_hls": bool(getattr(video, "is_hls", False)),
        "storage_name": storage_name,
        "play_url": play_url,
        "artwork_url": getattr(video, "artwork_url", "") or "",
    }


def _current_sponsor_payload() -> Optional[dict]:
    ad = SponsorAd.objects.filter(is_active=True).order_by("-id").first()
    if not ad:
        return None
    return {
        "title": ad.title,
        "description": ad.description,
        "image_url": ad.image_url,
        "click_url": ad.click_url,
    }


def _viewers_count(channel_obj: Channel, seconds_window: int = 60) -> int:
    """
    Count presences seen recently (simple "watching" metric).
    """
    cutoff = timezone.now() - timezone.timedelta(seconds=seconds_window)
    return Presence.objects.filter(channel=channel_obj, last_seen__gte=cutoff).count()


@dataclass
class PickResult:
    current_entry: Optional[ChannelEntry]
    seconds_into: int
    station_offset_seconds: int
    playlist_ids: List[int]


def _pick_now_from_rotation(channel_obj: Channel, entries: List[ChannelEntry]) -> PickResult:
    """
    Uses Channel.schedule_started_at as the station clock anchor so refresh doesn't restart.
    Rotates through entries based on each video's duration_seconds.
    """
    playlist_ids = [e.video_id for e in entries]

    if not entries:
        return PickResult(None, 0, 0, playlist_ids)

    # If any entry is explicitly live, prefer the first live entry
    for e in entries:
        if e.is_live:
            return PickResult(e, 0, 0, playlist_ids)

    durations = [int(getattr(e.video, "duration_seconds", 0) or 0) for e in entries]
    total = sum(d for d in durations if d > 0)

    # How long since station started
    station_elapsed = int((timezone.now() - channel_obj.schedule_started_at).total_seconds())
    if station_elapsed < 0:
        station_elapsed = 0

    # If total duration is 0, just pick the first entry
    if total <= 0:
        return PickResult(entries[0], 0, station_elapsed, playlist_ids)

    station_offset = station_elapsed % total

    # Walk the playlist to find the current entry and offset into it
    cursor = 0
    for e, d in zip(entries, durations):
        d = max(int(d or 0), 0)
        if d <= 0:
            continue

        if station_offset < cursor + d:
            seconds_into = station_offset - cursor
            # safety clamp
            if seconds_into < 0:
                seconds_into = 0
            if seconds_into >= d:
                seconds_into = d - 1
            return PickResult(e, int(seconds_into), int(station_offset), playlist_ids)

        cursor += d

    # Fallback (shouldn't happen)
    return PickResult(entries[0], 0, station_offset, playlist_ids)


# -------------------------
# Endpoints
# -------------------------
@require_GET
def now_json(request: HttpRequest, channel: Optional[str] = None):
    slug = _get_channel_slug(request, channel)

    # Ensure a Channel exists
    ch, _created = Channel.objects.get_or_create(
        slug=slug,
        defaults={
            "name": slug.title(),
            "is_default": (slug == "main"),
            "schedule_started_at": timezone.now(),
        },
    )

    entries = _active_entries_for_channel(ch)
    pick = _pick_now_from_rotation(ch, entries)

    sponsor = _current_sponsor_payload()
    viewers = _viewers_count(ch)

    payload_now = None
    if pick.current_entry:
        payload_now = _video_payload(pick.current_entry.video)

    # ✅ Return BOTH old + new schema keys (fixes black screen when JS expects item/current)
    return JsonResponse(
        {
            "ok": True,
            "channel": slug,
            "offset_seconds": int(pick.seconds_into),
            "station_offset_seconds": int(pick.station_offset_seconds),
            "viewers": viewers,
            "sponsor": sponsor,
            "playlist": pick.playlist_ids,
            "now": payload_now,       # new-ish schema
            "item": payload_now,      # older schema many frontends use
            "current": payload_now,   # extra compatibility
        }
    )


@require_GET
def messages_json(request: HttpRequest):
    slug = _get_channel_slug(request)
    ch, _ = Channel.objects.get_or_create(
        slug=slug,
        defaults={
            "name": slug.title(),
            "is_default": (slug == "main"),
            "schedule_started_at": timezone.now(),
        },
    )

    try:
        after_id = int(request.GET.get("after_id", "0") or 0)
    except Exception:
        after_id = 0

    qs = ChatMessage.objects.filter(channel=ch, id__gt=after_id).order_by("id")[:100]
    messages = []
    for m in qs:
        messages.append(
            {
                "id": m.id,
                "username": m.username,
                "message": m.message,
                "created_at": m.created_at.isoformat(),
            }
        )

    return JsonResponse({"ok": True, "messages": messages})


@require_GET
def ping_json(request: HttpRequest):
    slug = _get_channel_slug(request)
    ch, _ = Channel.objects.get_or_create(
        slug=slug,
        defaults={
            "name": slug.title(),
            "is_default": (slug == "main"),
            "schedule_started_at": timezone.now(),
        },
    )

    sid = (request.GET.get("sid") or "").strip()
    if sid:
        Presence.objects.update_or_create(
            channel=ch,
            sid=sid,
            defaults={"last_seen": timezone.now()},
        )

    return JsonResponse(
        {
            "ok": True,
            "channel": slug,
            "server_time": timezone.now().isoformat(),
            "watching": None,
        }
    )
