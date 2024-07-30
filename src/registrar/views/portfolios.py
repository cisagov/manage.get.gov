import logging
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.contrib import messages
from registrar.forms.portfolio import PortfolioOrgAddressForm
from registrar.models.portfolio import Portfolio
from registrar.views.utility.permission_views import (
    PortfolioDomainRequestsPermissionView,
    PortfolioDomainsPermissionView,
    PortfolioBasePermissionView,
)
from waffle.decorators import flag_is_active
from django.views.generic import View
from django.views.generic.edit import FormMixin


logger = logging.getLogger(__name__)


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


class PortfolioOrganizationView(PortfolioBasePermissionView, FormMixin):
    """
    View to handle displaying and updating the portfolio's organization details.
    """

    model = Portfolio
    template_name = "portfolio_organization.html"
    form_class = PortfolioOrgAddressForm
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        context = super().get_context_data(**kwargs)
        # no need to add portfolio to request context here

        context["has_edit_org_portfolio_permission"] = self.request.user.has_edit_org_portfolio_permission()

        context["has_profile_feature_flag"] = flag_is_active(self.request, "profile_feature")
        context["has_organization_feature_flag"] = flag_is_active(self.request, "organization_feature")
        return context

    def get_object(self, queryset=None):
        """Get the portfolio object based on the URL parameter."""
        return get_object_or_404(Portfolio, id=self.kwargs.get("portfolio_id"))

    def get_form_kwargs(self):
        """Include the instance in the form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def get(self, request, *args, **kwargs):
        """Handle GET requests to display the form."""
        self.object = self.get_object()
        form = self.get_form()
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        """Handle POST requests to process form submission."""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Handle the case when the form is valid."""
        self.object = form.save(commit=False)
        self.object.creator = self.request.user
        self.object.save()
        messages.success(self.request, "The organization information for this portfolio has been updated.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle the case when the form is invalid."""
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        """Redirect to the overview page for the portfolio."""
        return reverse("portfolio-organization", kwargs={"portfolio_id": self.object.pk})
