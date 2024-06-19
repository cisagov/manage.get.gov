from django.shortcuts import render
from waffle.decorators import flag_is_active


def index(request):
    """This page is available to anyone without logging in."""
    context = {}

    if request.user.is_authenticated:
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")

        # This controls the creation of a new domain request in the wizard
        request.session["new_request"] = True

    return render(request, "home.html", context)
