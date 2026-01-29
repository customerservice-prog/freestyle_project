from django.urls import path
from . import views

urlpatterns = [
    path("freestyle/channel/<slug:channel>/now.json", views.api_now, name="api_now"),
    path("freestyle/video/<int:video_id>/captions.json", views.api_captions, name="api_captions"),

    # chat
    path("chat/<slug:channel>/latest.json", views.api_chat_latest, name="api_chat_latest"),
    path("chat/<slug:channel>/post.json", views.api_chat_post, name="api_chat_post"),

    # reactions
    path("reactions/<slug:channel>/<slug:video_id>/counts.json", views.api_reaction_counts, name="api_reaction_counts"),
    path("reactions/<slug:channel>/<slug:video_id>/vote.json", views.api_reaction_vote, name="api_reaction_vote"),
]
