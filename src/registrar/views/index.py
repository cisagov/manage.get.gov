from django.shortcuts import render

from registrar.decorators import grant_access, ALL


@grant_access(ALL)
def index(request):
    """This page is available to anyone without logging in."""
    context = {}

    if request and request.user and request.user.is_authenticated:
        # This controls the creation of a new domain request in the wizard
        context["user_domain_count"] = request.user.get_user_domain_ids(request).count()
        context["num_expiring_domains"] = request.user.get_num_expiring_domains(request)

    return render(request, "home.html", context)
