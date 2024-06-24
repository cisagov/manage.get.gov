from django.shortcuts import get_object_or_404, render
from registrar.models.portfolio import Portfolio
from waffle.decorators import flag_is_active
from django.contrib.auth.decorators import login_required


@login_required
def portfolio_domains(request, portfolio_id):
    context = {}

    if request.user.is_authenticated:
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")
        context["has_organization_feature_flag"] = flag_is_active(request, "organization_feature")

        # Retrieve the portfolio object based on the provided portfolio_id
        portfolio = get_object_or_404(Portfolio, id=portfolio_id)
        context["portfolio"] = portfolio

    return render(request, "portfolio_domains.html", context)


@login_required
def portfolio_domain_requests(request, portfolio_id):
    context = {}

    if request.user.is_authenticated:
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")
        context["has_organization_feature_flag"] = flag_is_active(request, "organization_feature")

        # Retrieve the portfolio object based on the provided portfolio_id
        portfolio = get_object_or_404(Portfolio, id=portfolio_id)
        context["portfolio"] = portfolio

        # This controls the creation of a new domain request in the wizard
        request.session["new_request"] = True

    return render(request, "portfolio_requests.html", context)
