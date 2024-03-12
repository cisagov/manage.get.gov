from django.shortcuts import render

from registrar.models import DomainApplication, Domain, UserDomainRole


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        # Get all domain applications the user has access to
        applications, deletable_applications = _get_applications(request)

        context["domain_applications"] = applications

        # Get all domains the user has access to
        domains = _get_domains(request)
        context["domains"] = domains

        # Determine if the user will see applications that they can delete
        has_deletable_applications = deletable_applications.exists()
        context["has_deletable_applications"] = has_deletable_applications

        # If they can delete applications, add the delete button to the context
        if has_deletable_applications:
            # Add the delete modal button to the context
            modal_button = (
                '<button type="submit" '
                'class="usa-button usa-button--secondary" '
                'name="delete-application">Yes, delete request</button>'
            )
            context["modal_button"] = modal_button

    return render(request, "home.html", context)


def _get_applications(request):
    """Given the current request,
    get all DomainApplications that are associated with the UserDomainRole object.

    Returns a tuple of all applications, and those that are deletable by the user.
    """
    # Let's exclude the approved applications since our
    # domain_applications context will be used to populate
    # the active applications table
    applications = DomainApplication.objects.filter(creator=request.user).exclude(
        status=DomainApplication.ApplicationStatus.APPROVED
    )

    # Create a placeholder DraftDomain for each incomplete draft
    valid_statuses = [DomainApplication.ApplicationStatus.STARTED, DomainApplication.ApplicationStatus.WITHDRAWN]
    deletable_applications = applications.filter(status__in=valid_statuses)

    return (applications, deletable_applications)


def _get_domains(request):
    """Given the current request,
    get all domains that are associated with the UserDomainRole object"""
    user_domain_roles = UserDomainRole.objects.filter(user=request.user)
    domain_ids = user_domain_roles.values_list("domain_id", flat=True)
    return Domain.objects.filter(id__in=domain_ids)
