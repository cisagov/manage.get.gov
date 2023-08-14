from django.db.models import F
from django.db.models import F, Case, When, Value, BooleanField
from django.shortcuts import render

from registrar.models import DomainApplication, Domain
from django.db.models import Subquery


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        applications = DomainApplication.objects.filter(creator=request.user)
        # Exclude approved applications from the active table in home.html
        # TODO: exclude by application not exist for migrated domains?
        context["domain_applications"] = applications.exclude(status='approved')

        domains = request.user.permissions.values(
            "role",
            pk=F("domain__id"),
            name=F("domain__name"),
            created_time=F("domain__created_at"),
            application_status=F("domain__domain_application__status"),
        )
        # TODO: filter by application not exist for migrated domains?
        context["approved_domain_applications"] = domains.filter(application_status='approved')
    return render(request, "home.html", context)
