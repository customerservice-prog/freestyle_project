# freestyle/web_urls.py
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="freestyle/tv.html"), name="freestyle_tv"),
]
