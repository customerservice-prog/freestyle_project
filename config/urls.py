from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Root -> /freestyle/
    path("", RedirectView.as_view(url="/freestyle/", permanent=False)),

    path("admin/", admin.site.urls),

    # App pages
    path("freestyle/", include("freestyle.urls")),

    # API
    path("api/", include("api.urls")),
]

# Local dev: serve user-uploaded media so video_file.url works
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
