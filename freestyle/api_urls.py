from django.urls import path
from . import views

urlpatterns = [
    # Live TV
    path("freestyle/channel/<slug:channel>/now.json", views.api_now, name="api_now"),

    # Captions
    path("freestyle/video/<int:video_id>/captions.json", views.api_captions, name="api_captions"),
]
