from django.urls import path
from . import views

app_name = "freestyle"

urlpatterns = [
    path("", views.tv_page, name="tv"),
    path("submit/", views.submit_page, name="submit"),          # keep your existing view if you have it
    path("creator/", views.creator_page, name="creator"),       # keep your existing view if you have it
    path("control/freestyle/channel/<slug:slug>/", views.staff_channel, name="staff_channel"),  # keep if you have it
]
