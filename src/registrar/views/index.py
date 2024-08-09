from django.shortcuts import render


def index(request):
    """This page is available to anyone without logging in."""
    context = {}

    if request and request.user and request.user.is_authenticated:
        # This controls the creation of a new domain request in the wizard
        request.session["new_request"] = True
        context["user_domain_count"] = request.user.get_user_domain_ids(request).count()

    return render(request, "home.html", context)
