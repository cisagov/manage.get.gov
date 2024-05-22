from django.shortcuts import render
from registrar.models import DomainRequest
from waffle.decorators import flag_is_active


def index(request):
    """This page is available to anyone without logging in."""
    context = {}

    if request.user.is_authenticated:
        # Get all domain requests the user has access to
        domain_requests, deletable_domain_requests = _get_domain_requests(request)

        context["domain_requests"] = domain_requests

        # Determine if the user will see domain requests that they can delete
        has_deletable_domain_requests = deletable_domain_requests.exists()
        context["has_deletable_domain_requests"] = has_deletable_domain_requests

        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")

        # If they can delete domain requests, add the delete button to the context
        if has_deletable_domain_requests:
            # Add the delete modal button to the context
            modal_button = (
                '<button type="submit" '
                'class="usa-button usa-button--secondary" '
                'name="delete-domain-request">Yes, delete request</button>'
            )
            context["modal_button"] = modal_button

    return render(request, "home.html", context)


def _get_domain_requests(request):
    """Given the current request,
    get all DomainRequests that are associated with the UserDomainRole object.

    Returns a tuple of all domain requests, and those that are deletable by the user.
    """
    # Let's exclude the approved domain requests since our
    # domain_requests context will be used to populate
    # the active domain requests table
    domain_requests = DomainRequest.objects.filter(creator=request.user).exclude(
        status=DomainRequest.DomainRequestStatus.APPROVED
    )

    # Create a placeholder DraftDomain for each incomplete draft
    valid_statuses = [DomainRequest.DomainRequestStatus.STARTED, DomainRequest.DomainRequestStatus.WITHDRAWN]
    deletable_domain_requests = domain_requests.filter(status__in=valid_statuses)

    return (domain_requests, deletable_domain_requests)
