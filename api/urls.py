from django.urls import path
from . import views

urlpatterns = [
    # LIVE TV "now playing"
    path("freestyle/channel/<slug:slug>/now.json", views.channel_now_json, name="channel_now_json"),

    # Captions
    path("freestyle/video/<int:video_id>/captions.json", views.video_captions_json, name="video_captions_json"),
]
