from django.urls import path
from . import views

app_name = "tvapi"

urlpatterns = [
    path("channel/<slug:channel_slug>/now.json", views.now_json, name="now_json"),

    path("video/<int:video_id>/captions.json", views.captions_json, name="captions_json"),

    path("channel/<slug:channel_slug>/chat/messages.json", views.chat_messages_json, name="chat_messages_json"),
    path("channel/<slug:channel_slug>/chat/send/", views.chat_send, name="chat_send"),

    path("channel/<slug:channel_slug>/reactions/state.json", views.reaction_state_json, name="reaction_state_json"),
    path("channel/<slug:channel_slug>/reactions/vote/", views.reaction_vote, name="reaction_vote"),
]
