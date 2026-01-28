from django.urls import path
from .views import (
    CreatorLoginView, CreatorLogoutView,
    dashboard, upload, activate_set_password
)

urlpatterns = [
    path("", dashboard, name="creator_dashboard"),
    path("upload/", upload, name="creator_upload"),
    path("login/", CreatorLoginView.as_view(), name="creator_login"),
    path("logout/", CreatorLogoutView.as_view(), name="creator_logout"),
    path("activate/<slug:uidb64>/<slug:token>/", activate_set_password, name="creator_activate"),
]
