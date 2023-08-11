from django.db.models import F
from django.shortcuts import render

from registrar.models import DomainApplication, Domain
from django.db.models import Q, Subquery


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        applications = DomainApplication.objects.filter(creator=request.user)
        
        # Query to exclude apllications where the status is Approved or does not exist (applies to migrated domains)
        active_applications = applications.exclude(Q(status=True) | Q(status='approved'))
        
        context["domain_applications"] = active_applications

        domains = request.user.permissions.values(
            "role",
            pk=F("domain__id"),
            name=F("domain__name"),
            created_time=F("domain__created_at"),
            application_status=F("domain__domain_application__status"),
        )
        context["domains"] = domains
        
        # Query to filter domains where the application_status is Approved or does not exist (applies to migrated domains)
        approved_domains = domains.filter(Q(application_status__isnull=True) | Q(application_status='approved'))

        context["approved_domain_applications"] = approved_domains
    return render(request, "home.html", context)
