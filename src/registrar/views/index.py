from django.db.models import F
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from registrar.models import DomainApplication


@login_required
def index(request):
    """This page is available only to those that are logged in."""
    context = {}
    applications = DomainApplication.objects.filter(creator=request.user)
    context["domain_applications"] = applications

    domains = request.user.permissions.values(
        "role",
        pk=F("domain__id"),
        name=F("domain__name"),
        created_time=F("domain__created_at"),
        application_status=F("domain__domain_application__status"),
    )
    context["domains"] = domains
    return render(request, "home.html", context)
