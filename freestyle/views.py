from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def tv(request):
    return render(request, "freestyle/tv.html")
