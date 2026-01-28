from django.urls import path, include

urlpatterns = [
    # /api/freestyle/...
    path("freestyle/", include("freestyle.api_urls")),
]
