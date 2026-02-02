# freestyle/urls.py
from django.urls import path
from . import views
from . import tv_api_views

urlpatterns = [
    # -------------------------
    # Simple endpoints (what your TV page / JS likely expects)
    # -------------------------
    path("now.json", tv_api_views.now_json, name="tv_now_json"),
    path("messages.json", tv_api_views.messages_json, name="tv_messages_json"),
    path("ping.json", tv_api_views.ping_json, name="tv_ping_json"),

    # -------------------------
    # Pages
    # -------------------------
    path("", views.tv_page, name="tv"),
    path("freestyle/access/", views.access_page, name="access"),
    path("freestyle/submit/", views.submit_page, name="submit"),
    path("freestyle/creator/", views.creator_dashboard, name="creator_dashboard"),
    path("freestyle/creator/upload/", views.creator_upload, name="creator_upload"),

    # -------------------------
    # API (existing routes)
    # IMPORTANT: route the "now" endpoint to tv_api_views so video URLs are correct
    # -------------------------
    path(
        "api/freestyle/channel/<slug:channel>/now.json",
        tv_api_views.now_json,
        name="api_now_json",
    ),

    path("api/freestyle/presence/ping.json", views.presence_ping, name="presence_ping"),
    path(
        "api/freestyle/channel/<slug:channel>/chat/messages.json",
        views.chat_messages,
        name="chat_messages",
    ),
    path(
        "api/freestyle/channel/<slug:channel>/chat/send.json",
        views.chat_send,
        name="chat_send",
    ),

    path(
        "api/freestyle/channel/<slug:channel>/reactions/state.json",
        views.reaction_state,
        name="reaction_state",
    ),
    path(
        "api/freestyle/channel/<slug:channel>/reactions/vote.json",
        views.reaction_vote,
        name="reaction_vote",
    ),

    path(
        "api/freestyle/video/<int:video_id>/duration.json",
        views.save_duration_seconds,
        name="save_duration_seconds",
    ),
]
