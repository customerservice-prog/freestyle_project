from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CreatorUploadForm
from .models import CreatorProfile, FreestyleVideo
from .utils import get_or_create_main_channel, publish_video_to_channel


def _require_creator(user):
    try:
        return CreatorProfile.objects.get(user=user)
    except CreatorProfile.DoesNotExist:
        return None


@login_required
def dashboard(request):
    profile = _require_creator(request.user)
    if not profile:
        return render(request, "freestyle/creator/not_creator.html", status=403)

    published = FreestyleVideo.objects.filter(creator=profile, status=FreestyleVideo.STATUS_PUBLISHED).order_by("-published_at")
    pending = FreestyleVideo.objects.filter(creator=profile, status=FreestyleVideo.STATUS_PENDING).order_by("-created_at")
    return render(
        request,
        "freestyle/creator/dashboard.html",
        {"profile": profile, "published": published, "pending": pending},
    )


@login_required
def upload(request):
    profile = _require_creator(request.user)
    if not profile:
        return render(request, "freestyle/creator/not_creator.html", status=403)

    if request.method == "POST":
        form = CreatorUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.creator = profile
            # Trusted creators can auto-publish
            if profile.is_trusted:
                video.status = FreestyleVideo.STATUS_PUBLISHED
                video.save()
                channel = get_or_create_main_channel()
                publish_video_to_channel(video, channel)
                messages.success(request, "Uploaded and published ✅")
            else:
                video.status = FreestyleVideo.STATUS_PENDING
                video.save()
                messages.success(request, "Uploaded ✅ (waiting for review)")
            return redirect("freestyle_creator_dashboard")
    else:
        form = CreatorUploadForm()

    return render(request, "freestyle/creator/upload.html", {"form": form, "profile": profile})
