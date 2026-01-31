from django.urls import path
from freestyle.api import views as fv

urlpatterns = [
    # "Live TV" endpoint (what the player uses)
    path("freestyle/channel/<slug:channel_slug>/now.json", fv.channel_now, name="freestyle_now"),

    # Chat
    path("freestyle/channel/<slug:channel_slug>/chat/messages.json", fv.chat_messages, name="freestyle_chat_messages"),
    path("freestyle/channel/<slug:channel_slug>/chat/send.json", fv.chat_send, name="freestyle_chat_send"),

    # Reactions
    path("freestyle/channel/<slug:channel_slug>/reactions/state.json", fv.reactions_state, name="freestyle_reactions_state"),
    path("freestyle/channel/<slug:channel_slug>/reactions/vote.json", fv.reactions_vote, name="freestyle_reactions_vote"),
]
