from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # main app pages (/, /submit, /creator, etc)
    path("", include("freestyle.urls")),

    # API used by tv.js (DO NOT REMOVE — your JS calls /api/freestyle/...)
    path("api/freestyle/", include("freestyle.api_urls")),

    # OPTIONAL: only keep this if you actually still use tvapi routes
    # If tvapi is currently broken (VideoReaction import), comment it out for now.
    # path("tvapi/", include("tvapi.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
