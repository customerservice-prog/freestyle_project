# tvapi/urls.py
from django.urls import path
from . import views

app_name = "tvapi"

urlpatterns = [
    path("freestyle/channel/<slug:channel_slug>/now.json", views.channel_now_json, name="channel_now"),
    path("freestyle/video/<int:video_id>/captions.json", views.video_captions_json, name="video_captions"),

    path("freestyle/channel/<slug:channel_slug>/chat/messages.json", views.chat_messages_json, name="chat_messages"),
    path("freestyle/channel/<slug:channel_slug>/chat/send/", views.chat_send, name="chat_send"),

    path("freestyle/channel/<slug:channel_slug>/reactions/state.json", views.reactions_state, name="reactions_state"),
    path("freestyle/channel/<slug:channel_slug>/reactions/vote/", views.reactions_vote, name="reactions_vote"),
]
