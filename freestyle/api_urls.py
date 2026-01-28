from django.urls import path
from . import api_views

urlpatterns = [
    path("freestyle/channel/<slug:slug>/now.json", api_views.channel_now, name="freestyle_channel_now"),
    path("freestyle/channel/<slug:slug>/schedule.json", api_views.channel_schedule, name="freestyle_channel_schedule"),
    path("freestyle/video/<int:video_id>/stream", api_views.video_stream, name="freestyle_video_stream"),
    path("freestyle/video/<int:video_id>/captions.json", api_views.video_captions, name="freestyle_video_captions"),
]
