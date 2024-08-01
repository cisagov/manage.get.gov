from django.shortcuts import render
from registrar.views.utility.permission_views import (
    PortfolioDomainRequestsPermissionView,
    PortfolioDomainsPermissionView,
    PortfolioBasePermissionView,
)
from django.views.generic import View


class PortfolioDomainsView(PortfolioDomainsPermissionView, View):

    template_name = "portfolio_domains.html"

    def get(self, request):
        return render(request, "portfolio_domains.html")


class PortfolioDomainRequestsView(PortfolioDomainRequestsPermissionView, View):

    template_name = "portfolio_requests.html"

    def get(self, request):
        if self.request.user.is_authenticated:
            request.session["new_request"] = True
        return render(request, "portfolio_requests.html")


class PortfolioOrganizationView(PortfolioBasePermissionView, View):

    template_name = "portfolio_organization.html"

    def get(self, request):
        return render(request, "portfolio_organization.html")
