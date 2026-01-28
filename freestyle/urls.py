from django.urls import path
from . import views

urlpatterns = [
    # /freestyle/
    path("", views.tv, name="freestyle_tv"),
]
