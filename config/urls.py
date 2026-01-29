from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # API must exist on live:
    path("api/", include("api.urls")),

    # Freestyle pages:
    path("freestyle/", include("freestyle.urls")),
]

# Local dev media
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
