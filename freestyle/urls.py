# freestyle/urls.py
from django.urls import path
from . import views

app_name = "freestyle"

urlpatterns = [
    path("", views.tv_page, name="tv"),
    path("submit/", views.submit_page, name="submit"),
    path("manage/", views.manage_page, name="manage"),
    path("creator/", views.creator_page, name="creator"),
]
