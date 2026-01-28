from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_http_methods

from freestyle.models import ChannelEntry, FreestyleVideo, FreestyleSubmission, CreatorProfile
from freestyle.services.publishing import ensure_channel, publish_append_to_end

User = get_user_model()

# ---------- Channel manager (your current page) ----------
@staff_member_required
@require_http_methods(["GET", "POST"])
def channel_manage(request):
    channel = ensure_channel("main", "Main")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip() or "Untitled"
        duration_seconds = int(request.POST.get("duration_seconds") or 30)

        video_file = request.FILES.get("video_file")
        playback_url = (request.POST.get("playback_url") or "").strip()

        video = FreestyleVideo.objects.create(
            title=title,
            status=FreestyleVideo.Status.PUBLISHED,
            duration_seconds=max(1, duration_seconds),
            video_file=video_file if video_file else None,
            playback_url=playback_url if playback_url else "",
        )
        publish_append_to_end(video, channel_slug="main")
        return redirect("freestyle_channel_manage")

    entries = (
        ChannelEntry.objects
        .filter(channel=channel, active=True)
        .select_related("video")
        .order_by("position")
    )

    return render(request, "freestyle/control/channel_manage.html", {"channel": channel, "entries": entries})

@staff_member_required
@require_http_methods(["POST"])
def entry_delete(request, entry_id):
    entry = get_object_or_404(ChannelEntry, id=entry_id)
    entry.active = False
    entry.save(update_fields=["active"])
    return redirect("freestyle_channel_manage")


# ---------- Review queue ----------
@staff_member_required
def review_queue(request):
    pending = FreestyleSubmission.objects.filter(status=FreestyleSubmission.Status.PENDING).order_by("created_at")
    return render(request, "freestyle/control/review_queue.html", {"pending": pending})

@staff_member_required
def review_detail(request, submission_id):
    sub = get_object_or_404(FreestyleSubmission, id=submission_id)
    return render(request, "freestyle/control/review_detail.html", {"sub": sub})

def _get_or_create_creator(email: str):
    # Use email as username for simplicity
    user = User.objects.filter(username=email).first()
    created = False
    if not user:
        user = User.objects.create(username=email, email=email, is_active=True)
        user.set_unusable_password()
        user.save()
        created = True

    prof, _ = CreatorProfile.objects.get_or_create(user=user, defaults={"display_name": email.split("@")[0]})
    return user, prof, created

def _send_creator_activation_email(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(f"/freestyle/creator/activate/{uidb64}/{token}/")

    send_mail(
        subject="Your freestyle video was approved",
        message=f"Your video is approved ✅\n\nSet your password here:\n{link}\n\nThen log in and upload more videos.",
        from_email=None,
        recipient_list=[user.email],
        fail_silently=False,
    )

@staff_member_required
@require_http_methods(["POST"])
def approve(request, submission_id):
    sub = get_object_or_404(FreestyleSubmission, id=submission_id)
    if sub.status != FreestyleSubmission.Status.PENDING:
        return redirect("freestyle_review_queue")

    user, prof, created = _get_or_create_creator(sub.email)

    # Create a published video from the submission
    video = FreestyleVideo.objects.create(
        title=sub.title,
        status=FreestyleVideo.Status.PUBLISHED,
        duration_seconds=max(1, int(sub.duration_seconds or 30)),
        video_file=sub.video_file if sub.video_file else None,
        playback_url=sub.playback_url or "",
        creator=user,
    )
    publish_append_to_end(video, channel_slug="main")

    sub.status = FreestyleSubmission.Status.APPROVED
    sub.reviewed_at = timezone.now()
    sub.reviewer = request.user
    sub.creator = user
    sub.created_video = video
    sub.save(update_fields=["status", "reviewed_at", "reviewer", "creator", "created_video"])

    # Email creator login setup link (prints in terminal in dev)
    if created and user.email:
        _send_creator_activation_email(request, user)

    return redirect("freestyle_review_queue")

@staff_member_required
@require_http_methods(["POST"])
def reject(request, submission_id):
    sub = get_object_or_404(FreestyleSubmission, id=submission_id)
    if sub.status != FreestyleSubmission.Status.PENDING:
        return redirect("freestyle_review_queue")

    sub.status = FreestyleSubmission.Status.REJECTED
    sub.reviewed_at = timezone.now()
    sub.reviewer = request.user
    sub.save(update_fields=["status", "reviewed_at", "reviewer"])

    return redirect("freestyle_review_queue")
