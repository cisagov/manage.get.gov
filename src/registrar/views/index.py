from django.shortcuts import render
from registrar.models import DomainRequest
from waffle.decorators import flag_is_active


def index(request):
    """This page is available to anyone without logging in."""
    context = {}

    if request.user.is_authenticated:
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")

    return render(request, "home.html", context)
