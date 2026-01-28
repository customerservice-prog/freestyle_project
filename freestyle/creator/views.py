from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_http_methods

from freestyle.models import CreatorProfile, FreestyleSubmission, FreestyleVideo
from freestyle.services.publishing import publish_append_to_end
from .forms import CreatorUploadForm, SetPasswordForm

User = get_user_model()

class CreatorLoginView(LoginView):
    template_name = "freestyle/creator/login.html"

class CreatorLogoutView(LogoutView):
    pass

def _require_creator(user):
    return hasattr(user, "creator_profile")

@login_required
def dashboard(request):
    if not _require_creator(request.user):
        return HttpResponseForbidden("Not a creator account.")

    prof = request.user.creator_profile

    # Show creator’s published videos + pending submissions
    published = FreestyleVideo.objects.filter(creator=request.user).order_by("-created_at")[:50]
    pending = FreestyleSubmission.objects.filter(creator=request.user, status=FreestyleSubmission.Status.PENDING).order_by("-created_at")[:50]
    return render(request, "freestyle/creator/dashboard.html", {"prof": prof, "published": published, "pending": pending})

@login_required
@require_http_methods(["GET", "POST"])
def upload(request):
    if not _require_creator(request.user):
        return HttpResponseForbidden("Not a creator account.")

    prof: CreatorProfile = request.user.creator_profile

    if request.method == "POST":
        form = CreatorUploadForm(request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data["title"]
            duration_seconds = int(form.cleaned_data.get("duration_seconds") or 30)
            video_file = form.cleaned_data.get("video_file")
            playback_url = (form.cleaned_data.get("playback_url") or "").strip()

            if prof.is_trusted:
                # Auto-publish
                video = FreestyleVideo.objects.create(
                    title=title,
                    status=FreestyleVideo.Status.PUBLISHED,
                    duration_seconds=max(1, duration_seconds),
                    video_file=video_file if video_file else None,
                    playback_url=playback_url if playback_url else "",
                    creator=request.user,
                )
                publish_append_to_end(video, channel_slug="main")
                return redirect("/freestyle/creator/")
            else:
                # Require review
                FreestyleSubmission.objects.create(
                    title=title,
                    email=request.user.email or request.user.username,
                    video_file=video_file if video_file else None,
                    playback_url=playback_url if playback_url else "",
                    duration_seconds=max(1, duration_seconds),
                    status=FreestyleSubmission.Status.PENDING,
                    creator=request.user,
                )
                return redirect("/freestyle/creator/")

    else:
        form = CreatorUploadForm()

    return render(request, "freestyle/creator/upload.html", {"form": form, "prof": prof})

@require_http_methods(["GET", "POST"])
def activate_set_password(request, uidb64, token):
    try:
        uid = int(urlsafe_base64_decode(uidb64).decode())
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(request, "freestyle/creator/activate_set_password.html", {"invalid": True})

    if request.method == "POST":
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["password1"])
            user.save()
            # ensure creator profile exists
            CreatorProfile.objects.get_or_create(user=user, defaults={"display_name": user.username.split("@")[0]})
            return redirect("/freestyle/creator/login/")
    else:
        form = SetPasswordForm()

    return render(request, "freestyle/creator/activate_set_password.html", {"form": form, "invalid": False})
