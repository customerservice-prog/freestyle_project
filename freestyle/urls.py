from django.urls import path
from . import views

urlpatterns = [
    path("", views.freestyle_tv, name="freestyle_tv"),
    path("freestyle/", views.freestyle_tv),
    path("submit/", views.freestyle_submit, name="freestyle_submit"),
    path("creator/", views.freestyle_creator, name="freestyle_creator"),
]
