# freestyle/web_urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.freestyle_tv, name="freestyle_tv"),
]
