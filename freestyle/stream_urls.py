from django.urls import path
from . import stream_views

urlpatterns = [
    path("<path:file_path>", stream_views.stream_file, name="stream_file"),
]
