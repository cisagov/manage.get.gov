from django.shortcuts import get_object_or_404, render
from registrar.models.portfolio import Portfolio
from registrar.views.utility.permission_views import (
    PortfolioDomainRequestsPermissionView,
    PortfolioDomainsPermissionView,
    PortfolioBasePermissionView,
)
from waffle.decorators import flag_is_active
from django.views.generic import View


class PortfolioDomainsView(PortfolioDomainsPermissionView, View):

    template_name = "portfolio_domains.html"

    def get(self, request, portfolio_id):
        context = {}

        if self.request.user.is_authenticated:
            context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")
            context["has_organization_feature_flag"] = flag_is_active(request, "organization_feature")
            portfolio = get_object_or_404(Portfolio, id=portfolio_id)
            context["portfolio"] = portfolio

        return render(request, "portfolio_domains.html", context)


class PortfolioDomainRequestsView(PortfolioDomainRequestsPermissionView, View):

    template_name = "portfolio_requests.html"

    def get(self, request, portfolio_id):
        context = {}

        if self.request.user.is_authenticated:
            context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")
            context["has_organization_feature_flag"] = flag_is_active(request, "organization_feature")
            portfolio = get_object_or_404(Portfolio, id=portfolio_id)
            context["portfolio"] = portfolio
            request.session["new_request"] = True

        return render(request, "portfolio_requests.html", context)


class PortfolioOrganizationView(PortfolioBasePermissionView, View):

    template_name = "portfolio_organization.html"

    def get(self, request, portfolio_id):
        context = {}

        if self.request.user.is_authenticated:
            context["has_profile_feature_flag"] = flag_is_active(request, "profile_feature")
            context["has_organization_feature_flag"] = flag_is_active(request, "organization_feature")
            portfolio = get_object_or_404(Portfolio, id=portfolio_id)
            context["portfolio"] = portfolio

        return render(request, "portfolio_organization.html", context)
