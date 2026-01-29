from django.shortcuts import render

def tv_page(request):
    return render(request, "freestyle/tv.html")
