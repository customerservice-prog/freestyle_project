from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # App serves the TV page at "/" and also serves "/api/freestyle/..."
    path("", include("freestyle.urls")),
]

# DEV ONLY: serve uploaded media locally (Render serves it via the disk path directly)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
