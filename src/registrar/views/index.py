from django.shortcuts import render

from registrar.models import DomainApplication


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        # the logged-in index view IS the dashboard
        context["dashboard_view"] = True
        applications = DomainApplication.objects.filter(creator=request.user)
        context["domain_applications"] = applications
    return render(request, "home.html", context)
