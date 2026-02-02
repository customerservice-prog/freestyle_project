# config/urls.py
from django.contrib import admin
from django.urls import path, include

from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve

urlpatterns = [
    path("admin/", admin.site.urls),

    # Render health endpoint (does NOT depend on your TV page)
    path("api/health/", lambda request: JsonResponse({"ok": True})),

    # App serves TV page at "/" + your API routes
    path("", include("freestyle.urls")),
]

# Serve uploads in DEV, and also on Render when SERVE_MEDIA=1
if settings.DEBUG or getattr(settings, "SERVE_MEDIA", False):
    # static() only works reliably in DEBUG; for production we also add explicit serve()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Production-safe media serving route (Render disk)
    urlpatterns += [
        path(
            f"{settings.MEDIA_URL.lstrip('/')}" + "<path:path>",
            static_serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]
