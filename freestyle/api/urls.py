from django.urls import path
from . import views

urlpatterns = [
    path("freestyle/channel/<slug:slug>/now.json", views.channel_now, name="freestyle_channel_now"),
    path("freestyle/channel/<slug:slug>/schedule.json", views.channel_schedule, name="freestyle_channel_schedule"),

    # Range-enabled local MP4 stream (for live seeking)
    path("freestyle/video/<int:video_id>/stream", views.video_stream, name="freestyle_video_stream"),

    # ✅ Captions endpoint (new)
    path("freestyle/video/<int:video_id>/captions.json", views.video_captions, name="freestyle_video_captions"),
]

from django.urls import path
from . import views

urlpatterns = [
    # ... your other routes ...
    path("freestyle/video/<int:video_id>/captions.json", views.video_captions, name="freestyle_video_captions"),
]
