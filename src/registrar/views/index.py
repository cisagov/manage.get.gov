from django.db.models import F
from django.shortcuts import render

from registrar.models import DomainApplication


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        applications = DomainApplication.objects.filter(creator=request.user)
        # Let's exclude the approved applications since our
        # domain_applications context will be used to populate
        # the active applications table
        context["domain_applications"] = applications.exclude(status="approved")

        domains = request.user.permissions.values(
            "role",
            pk=F("domain__id"),
            name=F("domain__name"),
            created_time=F("domain__created_at"),
            state=F("domain__state"),
        )
        context["domains"] = domains
    return render(request, "home.html", context)
