# freestyle/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Pages
    path("", views.tv_page, name="tv"),
    path("freestyle/access/", views.access_page, name="access"),
    path("freestyle/submit/", views.submit_page, name="submit"),
    path("freestyle/creator/", views.creator_dashboard, name="creator_dashboard"),
    path("freestyle/creator/upload/", views.creator_upload, name="creator_upload"),

    # API (matches browser requests)
    path("api/freestyle/channel/<slug:channel>/now.json", views.now_json, name="now_json"),
    path("api/freestyle/presence/ping.json", views.presence_ping, name="presence_ping"),

    path("api/freestyle/channel/<slug:channel>/chat/messages.json", views.chat_messages, name="chat_messages"),
    path("api/freestyle/channel/<slug:channel>/chat/send.json", views.chat_send, name="chat_send"),

    path("api/freestyle/channel/<slug:channel>/reactions/state.json", views.reaction_state, name="reaction_state"),
    path("api/freestyle/channel/<slug:channel>/reactions/vote.json", views.reaction_vote, name="reaction_vote"),

    path("api/freestyle/video/<int:video_id>/duration.json", views.save_duration_seconds, name="save_duration_seconds"),
]
