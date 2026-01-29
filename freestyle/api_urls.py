from django.urls import path
from . import api_views

urlpatterns = [
    path("channel/<slug:channel_slug>/now.json", api_views.now_json, name="now_json"),

    path("video/<int:video_id>/captions.json", api_views.captions_json, name="captions_json"),

    path("channel/<slug:channel_slug>/chat/messages.json", api_views.chat_messages_json, name="chat_messages_json"),
    path("channel/<slug:channel_slug>/chat/send/", api_views.chat_send, name="chat_send"),

    path("channel/<slug:channel_slug>/reactions/state.json", api_views.reactions_state_json, name="reactions_state"),
    path("channel/<slug:channel_slug>/reactions/vote/", api_views.reactions_vote, name="reactions_vote"),
]
