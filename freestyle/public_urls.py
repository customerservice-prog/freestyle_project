# freestyle/public_urls.py
from django.urls import path
from . import public_views

urlpatterns = [
    path("", public_views.tv, name="freestyle_tv"),
]
