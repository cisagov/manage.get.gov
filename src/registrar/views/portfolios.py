import logging

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages

from registrar.forms import portfolio as portfolioForms
from registrar.models import Portfolio, User
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.views.utility.mixins import PortfolioMemberPermission
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
        if self.request.user.is_authenticated:
            request.session["new_request"] = True
        return render(request, "portfolio_requests.html")


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


class PortfolioMemberDeleteView(PortfolioMemberPermission, View):

    def post(self, request, pk):
        """
        Find and delete the portfolio member using the provided primary key (pk).
        Redirect to a success page after deletion (or any other appropriate page).
        """
        portfolio_member_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        member = portfolio_member_permission.user

        active_requests_count = member.get_active_requests_count_in_portfolio(request)

        support_url = "https://get.gov/contact/"

        error_message = ""

        if active_requests_count > 0:
            # If they have any in progress requests
            error_message = mark_safe(  # nosec
                f"This member has an active domain request and can't be removed from the organization. "
                f"<a href='{support_url}' target='_blank'>Contact the .gov team</a> to remove them."
            )
        elif member.is_only_admin_of_portfolio(portfolio_member_permission.portfolio):
            # If they are the last manager of a domain
            error_message = (
                "There must be at least one admin in your organization. Give another member admin "
                "permissions, make sure they log into the registrar, and then remove this member."
            )

        # From the Members Table page Else the Member Page
        if error_message:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )
            else:
                messages.error(request, error_message)
                return redirect(reverse("member", kwargs={"pk": pk}))

        # passed all error conditions
        portfolio_member_permission.delete()

        # From the Members Table page Else the Member Page
        success_message = f"You've removed {member.email} from the organization."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success_message}, status=200)
        else:
            messages.success(request, success_message)
            return redirect(reverse("members"))


class PortfolioMemberEditView(PortfolioMemberEditPermissionView, View):

    template_name = "portfolio_member_permissions.html"
    form_class = portfolioForms.PortfolioMemberForm

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


class PortfolioInvitedMemberDeleteView(PortfolioMemberPermission, View):

    def post(self, request, pk):
        """
        Find and delete the portfolio invited member using the provided primary key (pk).
        Redirect to a success page after deletion (or any other appropriate page).
        """
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)

        portfolio_invitation.delete()

        success_message = f"You've removed {portfolio_invitation.email} from the organization."
        # From the Members Table page Else the Member Page
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success_message}, status=200)
        else:
            messages.success(request, success_message)
            return redirect(reverse("members"))


class PortfolioInvitedMemberEditView(PortfolioMemberEditPermissionView, View):

    template_name = "portfolio_member_permissions.html"
    form_class = portfolioForms.PortfolioInvitedMemberForm

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
    form_class = portfolioForms.PortfolioOrgAddressForm
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
    form_class = portfolioForms.PortfolioSeniorOfficialForm
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


class PortfolioMembersView(PortfolioMembersPermissionView, View):

    template_name = "portfolio_members.html"

    def get(self, request):
        """Add additional context data to the template."""
        return render(request, "portfolio_members.html")


class NewMemberView(PortfolioMembersPermissionView, FormMixin):

    template_name = "portfolio_members_add_new.html"
    form_class = portfolioForms.NewMemberForm

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

    def form_invalid(self, form):
        """Handle the case when the form is invalid."""
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        """Redirect to members table."""
        return reverse("members")

    ##########################################
    # TODO: future ticket #2854
    # (save/invite new member)
    ##########################################

    # def _send_domain_invitation_email(self, email: str, requestor: User, add_success=True):
    #     """Performs the sending of the member invitation email
    #     email: string- email to send to
    #     add_success: bool- default True indicates:
    #     adding a success message to the view if the email sending succeeds

    #     raises EmailSendingError
    #     """

    #     # Set a default email address to send to for staff
    #     requestor_email = settings.DEFAULT_FROM_EMAIL

    #     # Check if the email requestor has a valid email address
    #     if not requestor.is_staff and requestor.email is not None and requestor.email.strip() != "":
    #         requestor_email = requestor.email
    #     elif not requestor.is_staff:
    #         messages.error(self.request, "Can't send invitation email. No email is associated with your account.")
    #         logger.error(
    #             f"Can't send email to '{email}' on domain '{self.object}'."
    #             f"No email exists for the requestor '{requestor.username}'.",
    #             exc_info=True,
    #         )
    #         return None

    #     # Check to see if an invite has already been sent
    #     try:
    #         invite = MemberInvitation.objects.get(email=email, domain=self.object)
    #         # check if the invite has already been accepted
    #         if invite.status == MemberInvitation.MemberInvitationStatus.RETRIEVED:
    #             add_success = False
    #             messages.warning(
    #                 self.request,
    #                 f"{email} is already a manager for this domain.",
    #             )
    #         else:
    #             add_success = False
    #             # else if it has been sent but not accepted
    #             messages.warning(self.request, f"{email} has already been invited to this domain")
    #     except Exception:
    #         logger.error("An error occured")

    #     try:
    #         send_templated_email(
    #             "emails/member_invitation.txt",
    #             "emails/member_invitation_subject.txt",
    #             to_address=email,
    #             context={
    #                 "portfolio": self.object,
    #                 "requestor_email": requestor_email,
    #             },
    #         )
    #     except EmailSendingError as exc:
    #         logger.warn(
    #             "Could not sent email invitation to %s for domain %s",
    #             email,
    #             self.object,
    #             exc_info=True,
    #         )
    #         raise EmailSendingError("Could not send email invitation.") from exc
    #     else:
    #         if add_success:
    #             messages.success(self.request, f"{email} has been invited to this domain.")

    # def _make_invitation(self, email_address: str, requestor: User):
    #     """Make a Member invitation for this email and redirect with a message."""
    #     try:
    #         self._send_member_invitation_email(email=email_address, requestor=requestor)
    #     except EmailSendingError:
    #         messages.warning(self.request, "Could not send email invitation.")
    #     else:
    #         # (NOTE: only create a MemberInvitation if the e-mail sends correctly)
    #         MemberInvitation.objects.get_or_create(email=email_address, domain=self.object)
    #     return redirect(self.get_success_url())

    # def form_valid(self, form):

    #     """Add the specified user as a member
    #     for this portfolio.
    #     Throws EmailSendingError."""
    #     requested_email = form.cleaned_data["email"]
    #     requestor = self.request.user
    #     # look up a user with that email
    #     try:
    #         requested_user = User.objects.get(email=requested_email)
    #     except User.DoesNotExist:
    #         # no matching user, go make an invitation
    #         return self._make_invitation(requested_email, requestor)
    #     else:
    #         # if user already exists then just send an email
    #         try:
    #             self._send_member_invitation_email(requested_email, requestor, add_success=False)
    #         except EmailSendingError:
    #             logger.warn(
    #                 "Could not send email invitation (EmailSendingError)",
    #                 self.object,
    #                 exc_info=True,
    #             )
    #             messages.warning(self.request, "Could not send email invitation.")
    #         except Exception:
    #             logger.warn(
    #                 "Could not send email invitation (Other Exception)",
    #                 self.object,
    #                 exc_info=True,
    #             )
    #             messages.warning(self.request, "Could not send email invitation.")

    #     try:
    #         UserPortfolioPermission.objects.create(
    #             user=requested_user,
    #             portfolio=self.object,
    #             role=UserDomainRole.Roles.MANAGER,
    #         )
    #     except IntegrityError:
    #         messages.warning(self.request, f"{requested_email} is already a member of this portfolio")
    #     else:
    #         messages.success(self.request, f"Added user {requested_email}.")
    #     return redirect(self.get_success_url())
