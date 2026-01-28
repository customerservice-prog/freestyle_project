from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # TV page
    path("freestyle/", include("freestyle.urls")),

    # API endpoints used by the TV
    path("api/", include("freestyle.api_urls")),
]
