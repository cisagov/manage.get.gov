from django.shortcuts import render

from registrar.models import DomainApplication, Domain, UserDomainRole


def index(request):
    """This page is available to anyone without logging in."""
    context = {}
    if request.user.is_authenticated:
        # Let's exclude the approved applications since our
        # domain_applications context will be used to populate
        # the active applications table
        applications = DomainApplication.objects.filter(creator=request.user).exclude(status="approved")

        # Pass the final context to the application
        context["domain_applications"] = applications

        user_domain_roles = UserDomainRole.objects.filter(user=request.user)
        domain_ids = user_domain_roles.values_list("domain_id", flat=True)
        domains = Domain.objects.filter(id__in=domain_ids)

        context["domains"] = domains

        # Determine if the user will see applications that they can delete
        valid_statuses = [DomainApplication.ApplicationStatus.STARTED, DomainApplication.ApplicationStatus.WITHDRAWN]
        has_deletable_applications = applications.filter(status__in=valid_statuses).exists()
        context["has_deletable_applications"] = has_deletable_applications

        if has_deletable_applications:
            modal_button = (
                '<button type="submit" '
                'class="usa-button usa-button--secondary" '
                'name="delete-application">Yes, delete request</button>'
            )

            context["modal_button"] = modal_button

    return render(request, "home.html", context)
