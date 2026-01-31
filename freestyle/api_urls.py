from django.urls import path
from . import api_views

urlpatterns = [
    path("presence/ping.json", api_views.presence_ping_json, name="presence_ping_json"),
    path("channel/<slug:channel>/now.json", api_views.now_json, name="now_json"),

    # IMPORTANT: MP4 streaming endpoint with Range support
    path("stream/<path:relpath>", api_views.stream_media, name="stream_media"),
]
