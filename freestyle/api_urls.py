from django.urls import path
from . import views

urlpatterns = [
    path("channel/<slug:channel>/now.json", views.now_json, name="freestyle_now_json"),
    path("presence/ping.json", views.presence_ping, name="freestyle_presence_ping"),

    path("channel/<slug:channel>/chat/messages.json", views.chat_messages, name="chat_messages"),
    path("channel/<slug:channel>/chat/send.json", views.chat_send, name="chat_send"),

    path("channel/<slug:channel>/reactions/state.json", views.reaction_state, name="reaction_state"),
    path("channel/<slug:channel>/reactions/vote.json", views.reaction_vote, name="reaction_vote"),

    path("video/<int:video_id>/captions.json", views.captions_json, name="captions_json"),
]
