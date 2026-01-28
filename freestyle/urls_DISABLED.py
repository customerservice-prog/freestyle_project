from django.urls import path
from . import public_views, creator_views, control_views

urlpatterns = [
    # Public
    path("", public_views.tv_home, name="freestyle_tv"),
    path("submit/", public_views.submit_video, name="freestyle_submit"),

    # Creator
    path("creator/", creator_views.dashboard, name="freestyle_creator_dashboard"),
    path("creator/upload/", creator_views.upload, name="freestyle_creator_upload"),

    # Control panel (staff only)
    path("control/freestyle/review/", control_views.review_queue, name="freestyle_control_review_queue"),
    path("control/freestyle/review/<int:submission_id>/", control_views.review_detail, name="freestyle_control_review_detail"),
    path("control/freestyle/review/<int:submission_id>/approve/", control_views.approve_submission, name="freestyle_control_review_approve"),
    path("control/freestyle/review/<int:submission_id>/reject/", control_views.reject_submission, name="freestyle_control_review_reject"),
    path("control/freestyle/channel/<slug:slug>/", control_views.channel_manager, name="freestyle_control_channel_manager"),
]
