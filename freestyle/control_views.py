from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Channel, ChannelEntry, CreatorProfile, FreestyleSubmission, FreestyleVideo
from .utils import ensure_creator_for_email, get_or_create_main_channel, publish_video_to_channel


@staff_member_required
def review_queue(request):
    pending = FreestyleSubmission.objects.filter(status=FreestyleSubmission.STATUS_PENDING).order_by("created_at")
    return render(request, "freestyle/control/review_queue.html", {"pending": pending})


@staff_member_required
def review_detail(request, submission_id: int):
    sub = get_object_or_404(FreestyleSubmission, id=submission_id)
    return render(request, "freestyle/control/review_detail.html", {"sub": sub})


@staff_member_required
def approve_submission(request, submission_id: int):
    sub = get_object_or_404(FreestyleSubmission, id=submission_id)
    if sub.status != FreestyleSubmission.STATUS_PENDING:
        return redirect("freestyle_control_review_queue")

    # Create/ensure creator account
    user, profile = ensure_creator_for_email(sub.email)

    # Create a video from submission
    video = FreestyleVideo.objects.create(
        title=sub.title,
        creator=profile,
        status=FreestyleVideo.STATUS_PUBLISHED,
        duration_seconds=sub.duration_seconds or 30,
        playback_url=sub.playback_url or "",
        video_file=sub.video_file,
        created_at=timezone.now(),
        published_at=timezone.now(),
    )

    # Publish (append to end)
    channel = get_or_create_main_channel()
    publish_video_to_channel(video, channel)

    sub.status = FreestyleSubmission.STATUS_APPROVED
    sub.save()

    # Send activation email (console backend prints it)
    sub.send_approved_email(request)

    return redirect("freestyle_control_review_queue")


@staff_member_required
def reject_submission(request, submission_id: int):
    sub = get_object_or_404(FreestyleSubmission, id=submission_id)
    sub.status = FreestyleSubmission.STATUS_REJECTED
    sub.save()
    return redirect("freestyle_control_review_queue")


@staff_member_required
def channel_manager(request, slug="main"):
    channel = get_object_or_404(Channel, slug=slug)
    entries = ChannelEntry.objects.filter(channel=channel, active=True).order_by("position")

    if request.method == "POST":
        # Delete button
        delete_entry_id = request.POST.get("delete_entry_id")
        if delete_entry_id:
            entry = get_object_or_404(ChannelEntry, id=delete_entry_id, channel=channel)
            entry.active = False
            entry.save()
            return redirect("freestyle_control_channel_manager", slug=slug)

    return render(request, "freestyle/control/channel_manager.html", {"channel": channel, "entries": entries})
