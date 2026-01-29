from django.http import HttpResponse
from django.shortcuts import render

def tv_page(request):
    return render(request, "freestyle/tv.html")

def submit_page(request):
    # create template freestyle/submit.html (simple stub ok)
    return render(request, "freestyle/submit.html")

def manage_page(request):
    return render(request, "freestyle/manage.html")

def creator_page(request):
    return render(request, "freestyle/creator.html")
