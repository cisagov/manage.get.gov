from django.shortcuts import render


def index(request):
    """This page is available to anyone without logging in."""
    return render(request, "home.html")
