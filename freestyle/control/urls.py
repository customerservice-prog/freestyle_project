from django.urls import path
from .views import (
    channel_manage, entry_delete,
    review_queue, review_detail, approve, reject
)

urlpatterns = [
    path("channel/", channel_manage, name="freestyle_channel_manage"),
    path("channel/entry/<int:entry_id>/delete/", entry_delete, name="freestyle_entry_delete"),

    path("review/", review_queue, name="freestyle_review_queue"),
    path("review/<int:submission_id>/", review_detail, name="freestyle_review_detail"),
    path("review/<int:submission_id>/approve/", approve, name="freestyle_review_approve"),
    path("review/<int:submission_id>/reject/", reject, name="freestyle_review_reject"),
]
