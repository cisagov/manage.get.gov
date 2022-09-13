from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def index(request):
    """This page is available to anyone without logging in."""
    return render(request, "home.html")
