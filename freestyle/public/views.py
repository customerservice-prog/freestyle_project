from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie

from .forms import PublicSubmissionForm


@ensure_csrf_cookie
def home(request):
    # TV screen page
    return render(request, "freestyle/public/home.html")


def submit(request):
    if request.method == "POST":
        form = PublicSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return render(request, "freestyle/public/submit_done.html")
    else:
        form = PublicSubmissionForm()

    return render(request, "freestyle/public/submit.html", {"form": form})
