# freestyle/public_views.py
from django.shortcuts import render

def tv(request):
    return render(request, "freestyle/tv.html")
