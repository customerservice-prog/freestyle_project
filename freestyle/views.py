from django.shortcuts import render

def freestyle_tv(request):
    return render(request, "freestyle/tv.html", {"channel_slug": "main"})

def freestyle_submit(request):
    return render(request, "freestyle/submit.html")

def freestyle_creator(request):
    return render(request, "freestyle/creator.html")
