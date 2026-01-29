from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # pages
    path("freestyle/", include("freestyle.urls")),

    # API (matches your tv.html JS: /api/freestyle/...)
    path("api/freestyle/", include("freestyle.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
