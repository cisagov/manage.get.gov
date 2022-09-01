from django.shortcuts import render

def index(request):
    context = {"name": "World!"}
    return render(request, "whoami.html", context)