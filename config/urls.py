# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

from freestyle.media_serve import media_serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("freestyle.urls")),
]

# DEV: Range-enabled media serving (fixes video playback reliability)
if settings.DEBUG:
    urlpatterns += [
        path("media/<path:path>", media_serve),
    ]
