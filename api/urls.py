from django.urls import path
from . import views

urlpatterns = [
    path("freestyle/channel/<slug:slug>/now.json", views.channel_now_json, name="channel_now_json"),
    path("freestyle/channel/<slug:slug>/playlist.json", views.channel_playlist_json, name="channel_playlist_json"),

    # ✅ critical: ranged streaming so refresh DOES NOT restart
    path("freestyle/video/<int:video_id>/stream", views.video_stream, name="video_stream"),

    # optional
    path("freestyle/video/<int:video_id>/captions.json", views.video_captions_json, name="video_captions_json"),
]
