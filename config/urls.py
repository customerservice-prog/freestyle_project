# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve

urlpatterns = [
    path("admin/", admin.site.urls),

    # Health endpoint
    path("api/health/", lambda request: JsonResponse({"ok": True})),

    # App routes (TV page + APIs)
    path("", include("freestyle.urls")),
]

# DEV convenience
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Production: serve media only if explicitly enabled (Render disk)
if getattr(settings, "SERVE_MEDIA", False):
    media_prefix = settings.MEDIA_URL.lstrip("/")
    urlpatterns += [
        re_path(rf"^{media_prefix}(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
