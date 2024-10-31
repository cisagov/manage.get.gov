import logging
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.contrib import messages
from registrar.forms.portfolio import (
    PortfolioInvitedMemberForm,
    PortfolioMemberForm,
    PortfolioOrgAddressForm,
    PortfolioSeniorOfficialForm,
)
from registrar.models import Portfolio, User
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.views.utility.permission_views import (
    PortfolioDomainRequestsPermissionView,
    PortfolioDomainsPermissionView,
    PortfolioBasePermissionView,
    NoPortfolioDomainsPermissionView,
    PortfolioMemberDomainsPermissionView,
    PortfolioMemberEditPermissionView,
    PortfolioMemberPermissionView,
    PortfolioMembersPermissionView,
)
from django.views.generic import View
from django.views.generic.edit import FormMixin
from django.shortcuts import get_object_or_404, redirect

logger = logging.getLogger(__name__)


class PortfolioDomainsView(PortfolioDomainsPermissionView, View):

    template_name = "portfolio_domains.html"

    def get(self, request):
        context = {}
        if self.request and self.request.user and self.request.user.is_authenticated:
            context["user_domain_count"] = self.request.user.get_user_domain_ids(request).count()
        return render(request, "portfolio_domains.html", context)


class PortfolioDomainRequestsView(PortfolioDomainRequestsPermissionView, View):

    template_name = "portfolio_requests.html"

    def get(self, request):
        return render(request, "portfolio_requests.html")


class PortfolioMembersView(PortfolioMembersPermissionView, View):

    template_name = "portfolio_members.html"

    def get(self, request):
        """Add additional context data to the template."""
        return render(request, "portfolio_members.html")


class PortfolioMemberView(PortfolioMemberPermissionView, View):

    template_name = "portfolio_member.html"

    def get(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        member = portfolio_permission.user

        # We have to explicitely name these with member_ otherwise we'll have conflicts with context preprocessors
        member_has_view_all_requests_portfolio_permission = member.has_view_all_requests_portfolio_permission(
            portfolio_permission.portfolio
        )
        member_has_edit_request_portfolio_permission = member.has_edit_request_portfolio_permission(
            portfolio_permission.portfolio
        )
        member_has_view_members_portfolio_permission = member.has_view_members_portfolio_permission(
            portfolio_permission.portfolio
        )
        member_has_edit_members_portfolio_permission = member.has_edit_members_portfolio_permission(
            portfolio_permission.portfolio
        )

        return render(
            request,
            self.template_name,
            {
                "edit_url": reverse("member-permissions", args=[pk]),
                "domains_url": reverse("member-domains", args=[pk]),
                "portfolio_permission": portfolio_permission,
                "member": member,
                "member_has_view_all_requests_portfolio_permission": member_has_view_all_requests_portfolio_permission,
                "member_has_edit_request_portfolio_permission": member_has_edit_request_portfolio_permission,
                "member_has_view_members_portfolio_permission": member_has_view_members_portfolio_permission,
                "member_has_edit_members_portfolio_permission": member_has_edit_members_portfolio_permission,
            },
        )


class PortfolioMemberEditView(PortfolioMemberEditPermissionView, View):

    template_name = "portfolio_member_permissions.html"
    form_class = PortfolioMemberForm

    def get(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        user = portfolio_permission.user

        form = self.form_class(instance=portfolio_permission)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "member": user,
            },
        )

    def post(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        user = portfolio_permission.user

        form = self.form_class(request.POST, instance=portfolio_permission)

        if form.is_valid():
            form.save()
            return redirect("member", pk=pk)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "member": user,  # Pass the user object again to the template
            },
        )


class PortfolioMemberDomainsView(PortfolioMemberDomainsPermissionView, View):

    template_name = "portfolio_member_domains.html"

    def get(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        member = portfolio_permission.user

        return render(
            request,
            self.template_name,
            {
                "portfolio_permission": portfolio_permission,
                "member": member,
            },
        )


class PortfolioInvitedMemberView(PortfolioMemberPermissionView, View):

    template_name = "portfolio_member.html"
    # form_class = PortfolioInvitedMemberForm

    def get(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)
        # form = self.form_class(instance=portfolio_invitation)

        # We have to explicitely name these with member_ otherwise we'll have conflicts with context preprocessors
        member_has_view_all_requests_portfolio_permission = (
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS in portfolio_invitation.get_portfolio_permissions()
        )
        member_has_edit_request_portfolio_permission = (
            UserPortfolioPermissionChoices.EDIT_REQUESTS in portfolio_invitation.get_portfolio_permissions()
        )
        member_has_view_members_portfolio_permission = (
            UserPortfolioPermissionChoices.VIEW_MEMBERS in portfolio_invitation.get_portfolio_permissions()
        )
        member_has_edit_members_portfolio_permission = (
            UserPortfolioPermissionChoices.EDIT_MEMBERS in portfolio_invitation.get_portfolio_permissions()
        )

        return render(
            request,
            self.template_name,
            {
                "edit_url": reverse("invitedmember-permissions", args=[pk]),
                "domains_url": reverse("invitedmember-domains", args=[pk]),
                "portfolio_invitation": portfolio_invitation,
                "member_has_view_all_requests_portfolio_permission": member_has_view_all_requests_portfolio_permission,
                "member_has_edit_request_portfolio_permission": member_has_edit_request_portfolio_permission,
                "member_has_view_members_portfolio_permission": member_has_view_members_portfolio_permission,
                "member_has_edit_members_portfolio_permission": member_has_edit_members_portfolio_permission,
            },
        )


class PortfolioInvitedMemberEditView(PortfolioMemberEditPermissionView, View):

    template_name = "portfolio_member_permissions.html"
    form_class = PortfolioInvitedMemberForm

    def get(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)
        form = self.form_class(instance=portfolio_invitation)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "invitation": portfolio_invitation,
            },
        )

    def post(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)
        form = self.form_class(request.POST, instance=portfolio_invitation)
        if form.is_valid():
            form.save()
            return redirect("invitedmember", pk=pk)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "invitation": portfolio_invitation,  # Pass the user object again to the template
            },
        )


class PortfolioInvitedMemberDomainsView(PortfolioMemberDomainsPermissionView, View):

    template_name = "portfolio_member_domains.html"

    def get(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)

        return render(
            request,
            self.template_name,
            {
                "portfolio_invitation": portfolio_invitation,
            },
        )


class PortfolioNoDomainsView(NoPortfolioDomainsPermissionView, View):
    """Some users have access to the underlying portfolio, but not any domains.
    This is a custom view which explains that to the user - and denotes who to contact.
    """

    model = Portfolio
    template_name = "portfolio_no_domains.html"

    def get(self, request):
        return render(request, self.template_name, context=self.get_context_data())

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        # We can override the base class. This view only needs this item.
        context = {}
        portfolio = self.request.session.get("portfolio")
        if portfolio:
            admin_ids = UserPortfolioPermission.objects.filter(
                portfolio=portfolio,
                roles__overlap=[
                    UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
                ],
            ).values_list("user__id", flat=True)

            admin_users = User.objects.filter(id__in=admin_ids)
            context["portfolio_administrators"] = admin_users
        return context


class PortfolioNoDomainRequestsView(NoPortfolioDomainsPermissionView, View):
    """Some users have access to the underlying portfolio, but not any domain requests.
    This is a custom view which explains that to the user - and denotes who to contact.
    """

    model = Portfolio
    template_name = "portfolio_no_requests.html"

    def get(self, request):
        return render(request, self.template_name, context=self.get_context_data())

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        # We can override the base class. This view only needs this item.
        context = {}
        portfolio = self.request.session.get("portfolio")
        if portfolio:
            admin_ids = UserPortfolioPermission.objects.filter(
                portfolio=portfolio,
                roles__overlap=[
                    UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
                ],
            ).values_list("user__id", flat=True)

            admin_users = User.objects.filter(id__in=admin_ids)
            context["portfolio_administrators"] = admin_users
        return context


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
        portfolio = self.request.session.get("portfolio")
        context["has_edit_org_portfolio_permission"] = self.request.user.has_edit_org_portfolio_permission(portfolio)
        return context

    def get_object(self, queryset=None):
        """Get the portfolio object based on the session."""
        portfolio = self.request.session.get("portfolio")
        if portfolio is None:
            raise Http404("No organization found for this user")
        return portfolio

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
        return reverse("organization")


class PortfolioSeniorOfficialView(PortfolioBasePermissionView, FormMixin):
    """
    View to handle displaying and updating the portfolio's senior official details.
    For now, this view is readonly.
    """

    model = Portfolio
    template_name = "portfolio_senior_official.html"
    form_class = PortfolioSeniorOfficialForm
    context_object_name = "portfolio"

    def get_object(self, queryset=None):
        """Get the portfolio object based on the session."""
        portfolio = self.request.session.get("portfolio")
        if portfolio is None:
            raise Http404("No organization found for this user")
        return portfolio

    def get_form_kwargs(self):
        """Include the instance in the form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object().senior_official
        return kwargs

    def get(self, request, *args, **kwargs):
        """Handle GET requests to display the form."""
        self.object = self.get_object()
        form = self.get_form()
        return self.render_to_response(self.get_context_data(form=form))
