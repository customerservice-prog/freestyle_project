# config/urls.py
from django.contrib import admin
from django.urls import path, include

from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve

urlpatterns = [
    path("admin/", admin.site.urls),

    # Health endpoint (does NOT depend on your TV page)
    path("api/health/", lambda request: JsonResponse({"ok": True})),

    # App routes (TV page at "/" + API routes)
    path("", include("freestyle.urls")),
]

# Serve uploads:
# - In DEBUG: use static()
# - In production: only if SERVE_MEDIA=1 (Render Disk)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if getattr(settings, "SERVE_MEDIA", False):
    media_prefix = settings.MEDIA_URL.lstrip("/")  # "media/"
    urlpatterns += [
        path(
            f"{media_prefix}<path:path>",
            static_serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]
