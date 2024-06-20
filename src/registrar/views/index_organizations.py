from django.shortcuts import render
from waffle.decorators import flag_is_active


def index_organizations(request, portfolio_id):
    """This page is available to anyone without logging in."""
    context = {}

    if request.user.is_authenticated:
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")
        context["has_organization_feature_flag"] = flag_is_active(request, "organization_feature")

        # This controls the creation of a new domain request in the wizard
        request.session["new_request"] = True

        print('homepage organizations view')

    return render(request, "home_organizations.html", context)
