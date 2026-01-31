# freestyle/api_urls.py
from django.urls import path
from . import api_views

urlpatterns = [
    path("channel/<slug:channel_slug>/now.json", api_views.channel_now, name="freestyle_channel_now"),

    # NEW: reset clock so offset starts at 0
    path("channel/<slug:channel_slug>/reset.json", api_views.channel_reset, name="freestyle_channel_reset"),

    path("channel/<slug:channel_slug>/chat/messages.json", api_views.chat_messages, name="freestyle_chat_messages"),
    path("channel/<slug:channel_slug>/chat/send.json", api_views.chat_send, name="freestyle_chat_send"),

    path("channel/<slug:channel_slug>/reactions/state.json", api_views.reactions_state, name="freestyle_reactions_state"),
    path("channel/<slug:channel_slug>/reactions/vote.json", api_views.reactions_vote, name="freestyle_reactions_vote"),

    path("video/<int:video_id>/captions.json", api_views.video_captions, name="freestyle_video_captions"),
]
