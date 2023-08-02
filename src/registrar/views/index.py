from django.db.models import F
from django.shortcuts import render

from registrar.models import DomainApplication


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        applications = DomainApplication.objects.filter(creator=request.user)
        context["domain_applications"] = applications

        domains = request.user.permissions.values(
            "role",
            pk=F("domain__id"),
            name=F("domain__name"),
            created_time=F("domain__created_at"),
        )
        context["domains"] = domains
    return render(request, "home.html", context)
