from django.urls import path
from . import views

urlpatterns = [
    # Live TV “now”
    path("freestyle/channel/<slug:slug>/now.json", views.channel_now_json, name="channel_now_json"),

    # Captions
    path("freestyle/video/<int:video_id>/captions.json", views.video_captions_json, name="video_captions_json"),

    # Chat
    path("freestyle/channel/<slug:slug>/chat/messages.json", views.chat_messages_json, name="chat_messages_json"),
    path("freestyle/channel/<slug:slug>/chat/send/", views.chat_send, name="chat_send"),

    # Reactions
    path("freestyle/channel/<slug:slug>/reactions/state.json", views.reaction_state_json, name="reaction_state_json"),
    path("freestyle/channel/<slug:slug>/reactions/vote/", views.reaction_vote, name="reaction_vote"),
]
