from django.utils import timezone
from django.shortcuts import render

from registrar.models import DomainApplication, Domain, UserDomainRole
from registrar.models.draft_domain import DraftDomain


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        # Let's exclude the approved applications since our
        # domain_applications context will be used to populate
        # the active applications table
        applications = DomainApplication.objects.filter(creator=request.user).exclude(status="approved")

        
        valid_statuses = [DomainApplication.ApplicationStatus.STARTED, DomainApplication.ApplicationStatus.WITHDRAWN]

        # Create a placeholder DraftDomain for each incomplete draft
        deletable_applications = applications.filter(status__in=valid_statuses, requested_domain=None)
        for application in applications:
            if application in deletable_applications:
                created_at = application.created_at.strftime("%b. %d, %Y, %I:%M %p UTC")
                _name = f"New domain request ({created_at})"
                default_draft_domain = DraftDomain(
                    name=_name,
                    is_complete=False
                )

                application.requested_domain = default_draft_domain

        # Pass the final context to the application
        context["domain_applications"] = applications

        user_domain_roles = UserDomainRole.objects.filter(user=request.user)
        domain_ids = user_domain_roles.values_list("domain_id", flat=True)
        domains = Domain.objects.filter(id__in=domain_ids)

        context["domains"] = domains

        # Determine if the user will see applications that they can delete
        has_deletable_applications = deletable_applications.exists()
        context["has_deletable_applications"] = has_deletable_applications
        if has_deletable_applications:

            # Add the delete modal button to the context
            modal_button = (
                '<button type="submit" '
                'class="usa-button usa-button--secondary" '
                'name="delete-application">Yes, delete request</button>'
            )
            context["modal_button"] = modal_button

    return render(request, "home.html", context)
