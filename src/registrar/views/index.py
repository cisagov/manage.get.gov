from django.shortcuts import render


def index(request):
    """This page is available to anyone without logging in."""
    context = {}

    if request.user.is_authenticated:
        # This controls the creation of a new domain request in the wizard
        request.session["new_request"] = True

    return render(request, "home.html", context)
