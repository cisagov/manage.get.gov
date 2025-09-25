import json
import logging

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from registrar.decorators import (
    HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM,
    HAS_PORTFOLIO_DOMAINS_ANY_PERM,
    HAS_PORTFOLIO_MEMBERS_ANY_PERM,
    HAS_PORTFOLIO_MEMBERS_EDIT,
    IS_PORTFOLIO_MEMBER,
    IS_MULTIPLE_PORTFOLIOS_MEMBER,
    grant_access,
)
from registrar.forms import portfolio as portfolioForms
from registrar.models import (
    Domain,
    DomainInvitation,
    Portfolio,
    PortfolioInvitation,
    User,
    UserDomainRole,
    UserPortfolioPermission,
)
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.utility.email import EmailSendingError
from registrar.utility.email_invitations import (
    send_domain_invitation_email,
    send_domain_manager_removal_emails_to_domain_managers,
    send_portfolio_admin_addition_emails,
    send_portfolio_admin_removal_emails,
    send_portfolio_invitation_email,
    send_portfolio_invitation_remove_email,
    send_portfolio_member_permission_remove_email,
    send_portfolio_member_permission_update_email,
    send_portfolio_update_emails_to_portfolio_admins,
)
from registrar.utility.errors import MissingEmailError
from registrar.utility.enums import DefaultUserValues
from django.views.generic import View, DetailView, ListView
from django.views.generic.edit import FormMixin
from django.db import IntegrityError

from registrar.views.utility.invitation_helper import get_org_membership


logger = logging.getLogger(__name__)


@grant_access(HAS_PORTFOLIO_DOMAINS_ANY_PERM)
class PortfolioDomainsView(View):

    template_name = "portfolio_domains.html"

    def get(self, request):
        context = {}
        if self.request and self.request.user and self.request.user.is_authenticated:
            context["user_domain_count"] = self.request.user.get_user_domain_ids(request).count()
            context["num_expiring_domains"] = request.user.get_num_expiring_domains(request)

        return render(request, "portfolio_domains.html", context)


@grant_access(HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM)
class PortfolioDomainRequestsView(View):

    template_name = "portfolio_requests.html"

    def get(self, request):
        return render(request, "portfolio_requests.html")


@grant_access(HAS_PORTFOLIO_MEMBERS_ANY_PERM)
class PortfolioMemberView(DetailView, View):
    model = Portfolio
    context_object_name = "portfolio"
    template_name = "portfolio_member.html"
    pk_url_kwarg = "member_pk"

    def get(self, request, member_pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=member_pk)
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
        member_has_view_all_domains_portfolio_permission = member.has_view_all_domains_portfolio_permission(
            portfolio_permission.portfolio
        )

        return render(
            request,
            self.template_name,
            {
                "edit_url": reverse("member-permissions", args=[member_pk]),
                "domains_url": reverse("member-domains", args=[member_pk]),
                "portfolio_permission": portfolio_permission,
                "member": member,
                "member_has_view_all_requests_portfolio_permission": member_has_view_all_requests_portfolio_permission,
                "member_has_edit_request_portfolio_permission": member_has_edit_request_portfolio_permission,
                "member_has_view_members_portfolio_permission": member_has_view_members_portfolio_permission,
                "member_has_edit_members_portfolio_permission": member_has_edit_members_portfolio_permission,
                "member_has_view_all_domains_portfolio_permission": member_has_view_all_domains_portfolio_permission,
                "is_only_admin": request.user.is_only_admin_of_portfolio(portfolio_permission.portfolio),
            },
        )


@grant_access(HAS_PORTFOLIO_MEMBERS_EDIT)
class PortfolioMemberDeleteView(View):
    pk_url_kwarg = "member_pk"

    def post(self, request, member_pk):
        """
        Find and delete the portfolio member using the provided primary key (pk).
        Redirect to a success page after deletion (or any other appropriate page).
        """
        portfolio_member_permission = get_object_or_404(UserPortfolioPermission, pk=member_pk)
        member = portfolio_member_permission.user
        portfolio = portfolio_member_permission.portfolio

        # Validate if the member can be removed
        error_message = self._validate_member_removal(request, member, portfolio)
        if error_message:
            return self._handle_error_response(request, error_message, member_pk)

        # Attempt to send notification emails
        self._send_removal_notifications(request, portfolio_member_permission)

        # Passed all error conditions, proceed with deletion
        portfolio_member_permission.delete()

        # Return success response
        return self._handle_success_response(request, member.email)

    def _validate_member_removal(self, request, member, portfolio):
        """
        Check whether the member can be removed from the portfolio.
        Returns an error message if removal is not allowed; otherwise, returns None.
        """
        active_requests_count = member.get_active_requests_count_in_portfolio(request)
        support_url = "https://get.gov/contact/"

        if active_requests_count > 0:
            return mark_safe(  # nosec
                "This member can't be removed from the organization because they have an active domain request. "
                f"Please <a class='usa-link' href='{support_url}' target='_blank'>contact us</a> to remove this member."
            )
        if member.is_only_admin_of_portfolio(portfolio):
            return (
                "You can't remove yourself because you're the only admin for this organization. "
                "To remove yourself, you'll need to add another admin."
            )
        return None

    def _handle_error_response(self, request, error_message, member_pk):
        """
        Return an error response (JSON or redirect with messages).
        """
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": error_message}, status=400)
        messages.error(request, error_message)
        return redirect(reverse("member", kwargs={"member_pk": member_pk}))

    def _send_removal_notifications(self, request, portfolio_member_permission):
        """
        Attempt to send notification emails about the member's removal.
        """
        try:
            # Notify other portfolio admins if removing an admin
            if UserPortfolioRoleChoices.ORGANIZATION_ADMIN in portfolio_member_permission.roles:
                if not send_portfolio_admin_removal_emails(
                    email=portfolio_member_permission.user.email,
                    requestor=request.user,
                    portfolio=portfolio_member_permission.portfolio,
                ):
                    messages.warning(request, "Could not send email notification to existing organization admins.")

            # Notify the member being removed
            if not send_portfolio_member_permission_remove_email(
                requestor=request.user, permissions=portfolio_member_permission
            ):
                messages.warning(
                    request, f"Could not send email notification to {portfolio_member_permission.user.email}"
                )

            # Notify domain managers for domains which the member is being removed from
            # Get list of portfolio domains that the member is invited to:
            invited_domains = Domain.objects.filter(
                invitations__email=portfolio_member_permission.user.email,
                domain_info__portfolio=portfolio_member_permission.portfolio,
                invitations__status=DomainInvitation.DomainInvitationStatus.INVITED,
            ).distinct()
            # Get list of portfolio domains that the member is a manager of
            domains = Domain.objects.filter(
                permissions__user=portfolio_member_permission.user,
                domain_info__portfolio=portfolio_member_permission.portfolio,
            ).distinct()
            # Combine both querysets while ensuring uniqueness
            all_domains = domains.union(invited_domains)
            for domain in all_domains:
                if not send_domain_manager_removal_emails_to_domain_managers(
                    removed_by_user=request.user,
                    manager_removed=portfolio_member_permission.user,
                    manager_removed_email=portfolio_member_permission.user.email,
                    domain=domain,
                ):
                    messages.warning(
                        request, "Could not send email notification to existing domain managers for %s", domain
                    )
        except Exception as e:
            self._handle_exceptions(e)

    def _handle_success_response(self, request, member_email):
        """
        Return a success response (JSON or redirect with messages).
        """
        success_message = f"You've removed {member_email} from the organization."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success_message}, status=200)
        messages.success(request, success_message)
        return redirect(reverse("members"))

    def _handle_exceptions(self, exception):
        """Handle exceptions raised during the process."""
        if isinstance(exception, MissingEmailError):
            messages.warning(self.request, "Could not send email notification to existing organization admins.")
            logger.warning(
                "Could not send email notification to existing organization admins.",
                exc_info=True,
            )
        else:
            logger.warning("Could not send email notification to existing organization admins.", exc_info=True)
            messages.warning(self.request, "Could not send email notification to existing organization admins.")


@grant_access(HAS_PORTFOLIO_MEMBERS_EDIT)
class PortfolioMemberEditView(DetailView, View):
    model = Portfolio
    context_object_name = "portfolio"
    template_name = "portfolio_member_permissions.html"
    form_class = portfolioForms.PortfolioMemberForm
    pk_url_kwarg = "member_pk"

    def get(self, request, member_pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=member_pk)
        user = portfolio_permission.user
        form = self.form_class(instance=portfolio_permission)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "member": user,
                "portfolio_permission": portfolio_permission,
                "is_only_admin": request.user.is_only_admin_of_portfolio(portfolio_permission.portfolio),
            },
        )

    def post(self, request, member_pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=member_pk)
        user = portfolio_permission.user
        form = self.form_class(request.POST, instance=portfolio_permission)
        removing_admin_role_on_self = False
        if form.is_valid():
            try:
                if form.is_change():
                    if not send_portfolio_member_permission_update_email(
                        requestor=request.user, permissions=form.instance
                    ):
                        messages.warning(self.request, f"Could not send email notification to {user.email}.")
                if form.is_change_from_member_to_admin():
                    if not send_portfolio_admin_addition_emails(
                        email=portfolio_permission.user.email,
                        requestor=request.user,
                        portfolio=portfolio_permission.portfolio,
                    ):
                        messages.warning(
                            self.request, "Could not send email notification to existing organization admins."
                        )
                elif form.is_change_from_admin_to_member():
                    if not send_portfolio_admin_removal_emails(
                        email=portfolio_permission.user.email,
                        requestor=request.user,
                        portfolio=portfolio_permission.portfolio,
                    ):
                        messages.warning(
                            self.request, "Could not send email notification to existing organization admins."
                        )
                    # Check if user is removing their own admin or edit role
                    removing_admin_role_on_self = request.user == user
            except Exception as e:
                self._handle_exceptions(e)
            form.save()
            messages.success(self.request, "The member role and permission changes have been saved.")
            return redirect("member", member_pk=member_pk) if not removing_admin_role_on_self else redirect("home")
        else:
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "member": user,
                    "portfolio_permission": portfolio_permission,
                    "is_only_admin": request.user.is_only_admin_of_portfolio(portfolio_permission.portfolio),
                },
            )

    def _handle_exceptions(self, exception):
        """Handle exceptions raised during the process."""
        if isinstance(exception, MissingEmailError):
            messages.warning(self.request, "Could not send email notification to existing organization admins.")
            logger.warning(
                "Could not send email notification to existing organization admins.",
                exc_info=True,
            )
        else:
            logger.warning("Could not send email notification to existing organization admins.", exc_info=True)
            messages.warning(self.request, "Could not send email notification to existing organization admins.")


@grant_access(HAS_PORTFOLIO_MEMBERS_ANY_PERM)
class PortfolioMemberDomainsView(View):

    template_name = "portfolio_member_domains.html"
    pk_url_kwarg = "member_pk"

    def get(self, request, member_pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=member_pk)
        member = portfolio_permission.user

        return render(
            request,
            self.template_name,
            {
                "portfolio_permission": portfolio_permission,
                "member": member,
            },
        )


@grant_access(HAS_PORTFOLIO_MEMBERS_EDIT)
class PortfolioMemberDomainsEditView(DetailView, View):
    model = Portfolio
    context_object_name = "portfolio"
    template_name = "portfolio_member_domains_edit.html"
    pk_url_kwarg = "member_pk"

    def get(self, request, member_pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=member_pk)
        member = portfolio_permission.user

        return render(
            request,
            self.template_name,
            {
                "portfolio_permission": portfolio_permission,
                "member": member,
            },
        )

    def post(self, request, member_pk):
        """
        Handles adding and removing domains for a portfolio member.
        """
        added_domains = request.POST.get("added_domains")
        removed_domains = request.POST.get("removed_domains")
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=member_pk)
        member = portfolio_permission.user
        portfolio = portfolio_permission.portfolio

        added_domain_ids = self._parse_domain_ids(added_domains, "added domains")
        if added_domain_ids is None:
            return redirect(reverse("member-domains", kwargs={"member_pk": member_pk}))

        removed_domain_ids = self._parse_domain_ids(removed_domains, "removed domains")
        if removed_domain_ids is None:
            return redirect(reverse("member-domains", kwargs={"member_pk": member_pk}))

        if not (added_domain_ids or removed_domain_ids):
            messages.success(request, "The domain assignment changes have been saved.")
            return redirect(reverse("member-domains", kwargs={"member_pk": member_pk}))

        try:
            self._process_added_domains(added_domain_ids, member, request.user, portfolio)
            self._process_removed_domains(removed_domain_ids, member)
            messages.success(request, "The domain assignment changes have been saved.")
            return redirect(reverse("member-domains", kwargs={"member_pk": member_pk}))
        except IntegrityError:
            messages.error(
                request,
                "A database error occurred while saving changes. If the issue persists, "
                f"please contact {DefaultUserValues.HELP_EMAIL}.",
            )
            logger.error("A database error occurred while saving changes.", exc_info=True)
            return redirect(reverse("member-domains-edit", kwargs={"member_pk": member_pk}))
        except Exception as e:
            messages.error(
                request,
                f"An unexpected error occurred: {str(e)}. If the issue persists, "
                f"please contact {DefaultUserValues.HELP_EMAIL}.",
            )
            logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
            return redirect(reverse("member-domains-edit", kwargs={"member_pk": member_pk}))

    def _parse_domain_ids(self, domain_data, domain_type):
        """
        Parses the domain IDs from the request and handles JSON errors.
        """
        try:
            return json.loads(domain_data) if domain_data else []
        except json.JSONDecodeError:
            messages.error(
                self.request,
                f"Invalid data for {domain_type}. If the issue persists, "
                f"please contact {DefaultUserValues.HELP_EMAIL}.",
            )
            logger.error(f"Invalid data for {domain_type}")
            return None

    def _process_added_domains(self, added_domain_ids, member, requestor, portfolio):
        """
        Processes added domains by bulk creating UserDomainRole instances.
        """
        if added_domain_ids:
            # get added_domains from ids to pass to send email method and bulk create
            added_domains = Domain.objects.filter(id__in=added_domain_ids)
            member_of_a_different_org, _ = get_org_membership(portfolio, member.email, member)
            if not send_domain_invitation_email(
                email=member.email,
                requestor=requestor,
                domains=added_domains,
                is_member_of_different_org=member_of_a_different_org,
                requested_user=member,
            ):
                messages.warning(self.request, "Could not send email notification to existing domain managers.")
            # Bulk create UserDomainRole instances for added domains
            UserDomainRole.objects.bulk_create(
                [
                    UserDomainRole(domain=domain, user=member, role=UserDomainRole.Roles.MANAGER)
                    for domain in added_domains
                ],
                ignore_conflicts=True,  # Avoid duplicate entries
            )

    def _process_removed_domains(self, removed_domain_ids, member):
        """
        Processes removed domains by deleting corresponding UserDomainRole instances.
        """
        if removed_domain_ids:
            # Notify domain managers for domains which the member is being removed from
            # Fetch Domain objects from removed_domain_ids
            removed_domains = Domain.objects.filter(id__in=removed_domain_ids)
            # need to get the domains from removed_domain_ids
            for domain in removed_domains:
                if not send_domain_manager_removal_emails_to_domain_managers(
                    removed_by_user=self.request.user,
                    manager_removed=member,
                    manager_removed_email=member.email,
                    domain=domain,
                ):
                    messages.warning(
                        self.request, "Could not send email notification to existing domain managers for %s", domain
                    )
            # Delete UserDomainRole instances for removed domains
            UserDomainRole.objects.filter(domain_id__in=removed_domain_ids, user=member).delete()


@grant_access(HAS_PORTFOLIO_MEMBERS_ANY_PERM)
class PortfolioInvitedMemberView(DetailView, View):
    model = Portfolio
    context_object_name = "portfolio"
    template_name = "portfolio_member.html"
    pk_url_kwarg = "invitedmember_pk"

    def get(self, request, invitedmember_pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=invitedmember_pk)

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
        member_has_view_all_domains_portfolio_permission = (
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS in portfolio_invitation.get_portfolio_permissions()
        )

        return render(
            request,
            self.template_name,
            {
                "edit_url": reverse("invitedmember-permissions", args=[invitedmember_pk]),
                "domains_url": reverse("invitedmember-domains", args=[invitedmember_pk]),
                "portfolio_invitation": portfolio_invitation,
                "member_has_view_all_requests_portfolio_permission": member_has_view_all_requests_portfolio_permission,
                "member_has_edit_request_portfolio_permission": member_has_edit_request_portfolio_permission,
                "member_has_view_members_portfolio_permission": member_has_view_members_portfolio_permission,
                "member_has_edit_members_portfolio_permission": member_has_edit_members_portfolio_permission,
                "member_has_view_all_domains_portfolio_permission": member_has_view_all_domains_portfolio_permission,
            },
        )


@grant_access(HAS_PORTFOLIO_MEMBERS_EDIT)
class PortfolioInvitedMemberDeleteView(View):
    pk_url_kwarg = "invitedmember_pk"

    def post(self, request, invitedmember_pk):
        """
        Find and delete the portfolio invited member using the provided primary key (pk).
        Redirect to a success page after deletion (or any other appropriate page).
        """
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=invitedmember_pk)

        try:
            # if invitation being removed is an admin
            if UserPortfolioRoleChoices.ORGANIZATION_ADMIN in portfolio_invitation.roles:
                # attempt to send notification emails of the removal to portfolio admins
                if not send_portfolio_admin_removal_emails(
                    email=portfolio_invitation.email, requestor=request.user, portfolio=portfolio_invitation.portfolio
                ):
                    messages.warning(self.request, "Could not send email notification to existing organization admins.")
            if not send_portfolio_invitation_remove_email(requestor=request.user, invitation=portfolio_invitation):
                messages.warning(request, f"Could not send email notification to {portfolio_invitation.email}")

            # Notify domain managers for domains which the invited member is being removed from
            # Get list of portfolio domains that the invited member is invited to:
            invited_domains = Domain.objects.filter(
                invitations__email=portfolio_invitation.email,
                domain_info__portfolio=portfolio_invitation.portfolio,
                invitations__status=DomainInvitation.DomainInvitationStatus.INVITED,
            ).distinct()
            # Get list of portfolio domains that the member is a manager of
            domains = Domain.objects.filter(
                permissions__user__email=portfolio_invitation.email,
                domain_info__portfolio=portfolio_invitation.portfolio,
            ).distinct()
            # Combine both querysets while ensuring uniqueness
            all_domains = domains.union(invited_domains)
            for domain in all_domains:
                if not send_domain_manager_removal_emails_to_domain_managers(
                    removed_by_user=request.user,
                    manager_removed=None,
                    manager_removed_email=portfolio_invitation.email,
                    domain=domain,
                ):
                    messages.warning(
                        request, "Could not send email notification to existing domain managers for %s", domain
                    )
        except Exception as e:
            self._handle_exceptions(e)

        portfolio_invitation.delete()

        success_message = f"You've removed {portfolio_invitation.email} from the organization."
        # From the Members Table page Else the Member Page
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success_message}, status=200)
        else:
            messages.success(request, success_message)
            return redirect(reverse("members"))

    def _handle_exceptions(self, exception):
        """Handle exceptions raised during the process."""
        if isinstance(exception, MissingEmailError):
            messages.warning(self.request, "Could not send email notification to existing organization admins.")
            logger.warning(
                "Could not send email notification to existing organization admins.",
                exc_info=True,
            )
        else:
            logger.warning("Could not send email notification to existing organization admins.", exc_info=True)
            messages.warning(self.request, "Could not send email notification to existing organization admins.")


@grant_access(HAS_PORTFOLIO_MEMBERS_EDIT)
class PortfolioInvitedMemberEditView(DetailView, View):
    model = Portfolio
    context_object_name = "portfolio"
    template_name = "portfolio_member_permissions.html"
    form_class = portfolioForms.PortfolioInvitedMemberForm
    pk_url_kwarg = "invitedmember_pk"

    def get(self, request, invitedmember_pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=invitedmember_pk)
        form = self.form_class(instance=portfolio_invitation)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "invitation": portfolio_invitation,
            },
        )

    def post(self, request, invitedmember_pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=invitedmember_pk)
        form = self.form_class(request.POST, instance=portfolio_invitation)
        if form.is_valid():
            try:
                if form.is_change_from_member_to_admin():
                    if not send_portfolio_admin_addition_emails(
                        email=portfolio_invitation.email,
                        requestor=request.user,
                        portfolio=portfolio_invitation.portfolio,
                    ):
                        messages.warning(
                            self.request, "Could not send email notification to existing organization admins."
                        )
                elif form.is_change_from_admin_to_member():
                    if not send_portfolio_admin_removal_emails(
                        email=portfolio_invitation.email,
                        requestor=request.user,
                        portfolio=portfolio_invitation.portfolio,
                    ):
                        messages.warning(
                            self.request, "Could not send email notification to existing organization admins."
                        )
            except Exception as e:
                self._handle_exceptions(e)
            form.save()
            messages.success(self.request, "The member role and permission changes have been saved.")
            return redirect("invitedmember", invitedmember_pk=invitedmember_pk)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "invitation": portfolio_invitation,  # Pass the user object again to the template
            },
        )

    def _handle_exceptions(self, exception):
        """Handle exceptions raised during the process."""
        if isinstance(exception, MissingEmailError):
            messages.warning(self.request, "Could not send email notification to existing organization admins.")
            logger.warning(
                "Could not send email notification to existing organization admins.",
                exc_info=True,
            )
        else:
            logger.warning("Could not send email notification to existing organization admins.", exc_info=True)
            messages.warning(self.request, "Could not send email notification to existing organization admins.")


@grant_access(HAS_PORTFOLIO_MEMBERS_ANY_PERM)
class PortfolioInvitedMemberDomainsView(View):

    template_name = "portfolio_member_domains.html"
    pk_url_kwarg = "invitedmember_pk"

    def get(self, request, invitedmember_pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=invitedmember_pk)

        return render(
            request,
            self.template_name,
            {
                "portfolio_invitation": portfolio_invitation,
            },
        )


@grant_access(HAS_PORTFOLIO_MEMBERS_EDIT)
class PortfolioInvitedMemberDomainsEditView(DetailView, View):

    model = Portfolio
    context_object_name = "portfolio"
    template_name = "portfolio_member_domains_edit.html"
    pk_url_kwarg = "invitedmember_pk"

    def get(self, request, invitedmember_pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=invitedmember_pk)

        return render(
            request,
            self.template_name,
            {
                "portfolio_invitation": portfolio_invitation,
            },
        )

    def post(self, request, invitedmember_pk):
        """
        Handles adding and removing domains for a portfolio invitee.
        """
        added_domains = request.POST.get("added_domains")
        removed_domains = request.POST.get("removed_domains")
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=invitedmember_pk)
        email = portfolio_invitation.email
        portfolio = portfolio_invitation.portfolio

        added_domain_ids = self._parse_domain_ids(added_domains, "added domains")
        if added_domain_ids is None:
            return redirect(reverse("invitedmember-domains", kwargs={"invitedmember_pk": invitedmember_pk}))

        removed_domain_ids = self._parse_domain_ids(removed_domains, "removed domains")
        if removed_domain_ids is None:
            return redirect(reverse("invitedmember-domains", kwargs={"invitedmember_pk": invitedmember_pk}))

        if not (added_domain_ids or removed_domain_ids):
            messages.success(request, "The domain assignment changes have been saved.")
            return redirect(reverse("invitedmember-domains", kwargs={"invitedmember_pk": invitedmember_pk}))

        try:
            self._process_added_domains(added_domain_ids, email, request.user, portfolio)
            self._process_removed_domains(removed_domain_ids, email)
            messages.success(request, "The domain assignment changes have been saved.")
            return redirect(reverse("invitedmember-domains", kwargs={"invitedmember_pk": invitedmember_pk}))
        except IntegrityError:
            messages.error(
                request,
                "A database error occurred while saving changes. If the issue persists, "
                f"please contact {DefaultUserValues.HELP_EMAIL}.",
            )
            logger.error("A database error occurred while saving changes.", exc_info=True)
            return redirect(reverse("invitedmember-domains-edit", kwargs={"invitedmember_pk": invitedmember_pk}))
        except Exception as e:
            messages.error(
                request,
                f"An unexpected error occurred: {str(e)}. If the issue persists, "
                f"please contact {DefaultUserValues.HELP_EMAIL}.",
            )
            logger.error(f"An unexpected error occurred: {str(e)}.", exc_info=True)
            return redirect(reverse("invitedmember-domains-edit", kwargs={"invitedmember_pk": invitedmember_pk}))

    def _parse_domain_ids(self, domain_data, domain_type):
        """
        Parses the domain IDs from the request and handles JSON errors.
        """
        try:
            return json.loads(domain_data) if domain_data else []
        except json.JSONDecodeError:
            messages.error(
                self.request,
                f"Invalid data for {domain_type}. If the issue persists, "
                f"please contact {DefaultUserValues.HELP_EMAIL}.",
            )
            logger.error(f"Invalid data for {domain_type}.")
            return None

    def _process_added_domains(self, added_domain_ids, email, requestor, portfolio):
        """
        Processes added domain invitations by updating existing invitations
        or creating new ones.
        """
        if added_domain_ids:
            # get added_domains from ids to pass to send email method and bulk create
            added_domains = Domain.objects.filter(id__in=added_domain_ids)
            member_of_a_different_org, _ = get_org_membership(portfolio, email, None)
            if not send_domain_invitation_email(
                email=email,
                requestor=requestor,
                domains=added_domains,
                is_member_of_different_org=member_of_a_different_org,
            ):
                messages.warning(self.request, "Could not send email notification to existing domain managers.")

            # Update existing invitations from CANCELED to INVITED
            existing_invitations = DomainInvitation.objects.filter(domain__in=added_domains, email=email)
            existing_invitations.update(status=DomainInvitation.DomainInvitationStatus.INVITED)

            # Determine which domains need new invitations
            existing_domain_ids = existing_invitations.values_list("domain_id", flat=True)
            new_domain_ids = set(added_domain_ids) - set(existing_domain_ids)

            # Bulk create new invitations
            DomainInvitation.objects.bulk_create(
                [
                    DomainInvitation(
                        domain_id=domain_id,
                        email=email,
                        status=DomainInvitation.DomainInvitationStatus.INVITED,
                    )
                    for domain_id in new_domain_ids
                ]
            )

    def _process_removed_domains(self, removed_domain_ids, email):
        """
        Processes removed domain invitations by updating their status to CANCELED.
        """
        if not removed_domain_ids:
            return

        # Notify domain managers for domains which the member is being removed from
        # Fetch Domain objects from removed_domain_ids
        removed_domains = Domain.objects.filter(id__in=removed_domain_ids)
        # need to get the domains from removed_domain_ids
        for domain in removed_domains:
            if not send_domain_manager_removal_emails_to_domain_managers(
                removed_by_user=self.request.user,
                manager_removed=None,
                manager_removed_email=email,
                domain=domain,
            ):
                messages.warning(
                    self.request, "Could not send email notification to existing domain managers for %s", domain
                )

        # Update invitations from INVITED to CANCELED
        DomainInvitation.objects.filter(
            domain_id__in=removed_domain_ids,
            email=email,
            status=DomainInvitation.DomainInvitationStatus.INVITED,
        ).update(status=DomainInvitation.DomainInvitationStatus.CANCELED)


@grant_access(IS_PORTFOLIO_MEMBER)
class PortfolioNoDomainsView(View):
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


@grant_access(IS_PORTFOLIO_MEMBER)
class PortfolioNoDomainRequestsView(View):
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


@grant_access(IS_PORTFOLIO_MEMBER)
class PortfolioOrganizationView(DetailView):
    """
    View to handle displaying and updating overview of portfolio's information.
    """

    model = Portfolio
    template_name = "portfolio_organization.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        context = super().get_context_data(**kwargs)
        portfolio = self.request.session.get("portfolio")
        context["has_edit_portfolio_permission"] = self.request.user.has_edit_portfolio_permission(portfolio)
        context["portfolio_admins"] = portfolio.portfolio_admin_users
        context["organization_type"] = portfolio.get_organization_type_display()
        if context["organization_type"] == "Federal":
            context["federal_type"] = portfolio.federal_agency.get_federal_type_display()
        return context

    def get_object(self, queryset=None):
        """Get the portfolio object based on the session."""
        portfolio = self.request.session.get("portfolio")
        if portfolio is None:
            raise Http404("No organization found for this user")
        return portfolio

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


@grant_access(IS_PORTFOLIO_MEMBER)
class PortfolioOrganizationInfoView(DetailView, FormMixin):
    """
    View to handle displaying and updating the portfolio's organization details.
    """

    model = Portfolio
    template_name = "portfolio_organization_info.html"
    form_class = portfolioForms.PortfolioOrgAddressForm
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        context = super().get_context_data(**kwargs)
        portfolio = self.request.session.get("portfolio")
        context["has_edit_portfolio_permission"] = self.request.user.has_edit_portfolio_permission(portfolio)
        context["portfolio_admins"] = portfolio.portfolio_admin_users
        context["organization_type"] = portfolio.get_organization_type_display()
        if context["organization_type"] == "Federal":
            context["federal_type"] = portfolio.federal_agency.get_federal_type_display()
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
            user = request.user
            try:
                if not send_portfolio_update_emails_to_portfolio_admins(
                    editor=user, portfolio=self.request.session.get("portfolio"), updated_page="Organization"
                ):
                    messages.warning(self.request, "Could not send email notification to all organization admins.")
            except Exception as e:
                messages.error(
                    request,
                    f"An unexpected error occurred: {str(e)}. If the issue persists, "
                    f"please contact {DefaultUserValues.HELP_EMAIL}.",
                )
                logger.error(f"An unexpected error occurred: {str(e)}.", exc_info=True)
                return None
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Handle the case when the form is valid."""
        self.object = form.save(commit=False)
        self.object.requester = self.request.user
        self.object.save()
        messages.success(self.request, "The organization information for this portfolio has been updated.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle the case when the form is invalid."""
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        """Redirect to the org info page for the portfolio."""
        return reverse("organization-info")


@grant_access(IS_PORTFOLIO_MEMBER)
class PortfolioSeniorOfficialView(DetailView, FormMixin):
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

    def post(self, request, *args, **kwargs):
        """Handle POST requests to process form submission."""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            user = request.user
            try:
                if not send_portfolio_update_emails_to_portfolio_admins(
                    editor=user, portfolio=self.request.session.get("portfolio"), updated_page="Senior Official"
                ):
                    messages.warning(self.request, "Could not send email notification to all organization admins.")
            except Exception as e:
                messages.error(
                    request,
                    f"An unexpected error occurred: {str(e)}. If the issue persists, "
                    f"please contact {DefaultUserValues.HELP_EMAIL}.",
                )
                logger.error(f"An unexpected error occurred: {str(e)}.", exc_info=True)
                return None
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Handle the case when the form is valid."""
        self.object = form.save(commit=False)
        self.object.requester = self.request.user
        self.object.save()
        messages.success(self.request, "The senior official information for this portfolio has been updated.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle the case when the form is invalid."""
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        """Redirect to the overview page for the portfolio."""
        return reverse("organization-senior-official")


@grant_access(HAS_PORTFOLIO_MEMBERS_ANY_PERM)
class PortfolioMembersView(View):

    template_name = "portfolio_members.html"

    def get(self, request):
        """Add additional context data to the template."""
        return render(request, "portfolio_members.html")


@grant_access(HAS_PORTFOLIO_MEMBERS_EDIT)
class PortfolioAddMemberView(DetailView, FormMixin):

    template_name = "portfolio_members_add_new.html"
    form_class = portfolioForms.PortfolioNewMemberForm
    model = Portfolio
    context_object_name = "portfolio"

    def get(self, request, *args, **kwargs):
        """Handle GET requests to display the form."""
        self.object = None  # No existing PortfolioInvitation instance
        form = self.get_form()
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        """Handle POST requests to process form submission."""
        self.object = None  # For a new invitation, there's no existing model instance

        # portfolio not submitted with form, so override the value
        data = request.POST.copy()
        if not data.get("portfolio"):
            data["portfolio"] = self.request.session.get("portfolio").id
        # Pass the modified data to the form
        form = portfolioForms.PortfolioNewMemberForm(data)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def is_ajax(self):
        return self.request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def form_invalid(self, form):
        if self.is_ajax():
            return JsonResponse({"is_valid": False})  # Return a JSON response
        else:
            return super().form_invalid(form)  # Handle non-AJAX requests normally

    def form_valid(self, form):
        super().form_valid(form)
        if self.is_ajax():
            return JsonResponse({"is_valid": True})  # Return a JSON response
        else:
            return self.submit_new_member(form)

    def get_success_url(self):
        """Redirect to members table."""
        return reverse("members")

    def submit_new_member(self, form):
        """Add the specified user as a member for this portfolio."""
        requested_email = form.cleaned_data["email"]
        requestor = self.request.user
        portfolio = form.cleaned_data["portfolio"]
        is_admin_invitation = UserPortfolioRoleChoices.ORGANIZATION_ADMIN in form.cleaned_data["roles"]

        requested_user = User.objects.filter(email__iexact=requested_email).first()
        permission_exists = UserPortfolioPermission.objects.filter(user=requested_user, portfolio=portfolio).exists()
        try:
            if not requested_user or not permission_exists:
                if not send_portfolio_invitation_email(
                    email=requested_email,
                    requestor=requestor,
                    portfolio=portfolio,
                    is_admin_invitation=is_admin_invitation,
                ):
                    messages.warning(self.request, "Could not send email notification to existing organization admins.")
                portfolio_invitation = form.save()
                # if user exists for email, immediately retrieve portfolio invitation upon creation
                if requested_user is not None:
                    portfolio_invitation.retrieve()
                    portfolio_invitation.save()
                messages.success(self.request, f"{requested_email} has been invited.")
            else:
                if permission_exists:
                    messages.warning(self.request, "User is already a member of this portfolio.")
        except Exception as e:
            self._handle_exceptions(e, portfolio, requested_email)
        return redirect(self.get_success_url())

    def _handle_exceptions(self, exception, portfolio, email):
        """Handle exceptions raised during the process."""
        if isinstance(exception, EmailSendingError):
            logger.warning(
                "Could not sent email invitation to %s for portfolio %s (EmailSendingError)",
                email,
                portfolio,
                exc_info=True,
            )
            messages.error(self.request, "Could not send organization invitation email.")
        elif isinstance(exception, MissingEmailError):
            messages.error(self.request, str(exception))
            logger.error(
                f"Can't send invitation email. No email is associated with your account.",
                exc_info=True,
            )
        else:
            logger.warning("Could not send email invitation (Other Exception)", exc_info=True)
            messages.warning(self.request, "Could not send portfolio email invitation.")


@grant_access(IS_MULTIPLE_PORTFOLIOS_MEMBER)
class PortfolioOrganizationsDropdownView(ListView, FormMixin):
    """
    View for Organizations dropdown.
    Actual session switching is handled in PortfolioOrganizationSelectView.
    """

    model = UserPortfolioPermission
    template_name = "portfolio_organizations_dropdown.html"
    context_object_name = "portfolio"
    pk_url_kwarg = "portfolio_pk"
    form_class = portfolioForms.PortfolioOrganizationSelectForm

    def get(self, request):
        """Add additional context data to the template."""
        return render(request, "portfolio_organizations.html", context=self.get_context_data())

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        # We can override the base class. This view only needs this item.
        context = {}
        user_portfolio_permissions = UserPortfolioPermission.objects.filter(user=self.request.user).order_by(
            "portfolio"
        )
        context["user_portfolio_permissions"] = user_portfolio_permissions
        return context


@grant_access(IS_MULTIPLE_PORTFOLIOS_MEMBER)
class PortfolioOrganizationsView(ListView, FormMixin):
    """
    View for Select Portfolio Organization page when the user does not
    have an active portfolio in session. Actual session switching is
    handled in PortfolioOrganizationSelectView.
    """

    model = UserPortfolioPermission
    template_name = "portfolio_organizations.html"
    context_object_name = "portfolio"
    pk_url_kwarg = "portfolio_pk"
    form_class = portfolioForms.PortfolioOrganizationSelectForm

    def get(self, request):
        """Add additional context data to the template."""
        return render(request, "portfolio_organizations.html", context=self.get_context_data())

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        # We can override the base class. This view only needs this item.
        context = {}
        user_portfolio_permissions = UserPortfolioPermission.objects.filter(user=self.request.user).order_by(
            "portfolio"
        )
        context["user_portfolio_permissions"] = user_portfolio_permissions
        return context

    def post(self, request, *args, **kwargs):
        """
        Handles updating active portfolio in session.
        """
        self.object = self.get_object()
        self.form = self.get_form()


@grant_access(IS_MULTIPLE_PORTFOLIOS_MEMBER)
class PortfolioOrganizationSelectView(DetailView, FormMixin):
    """
    View that displays an individual portfolio object and sets
    active session portfolio to said portfolio when selected.
    """

    model = UserPortfolioPermission
    template_name = "portfolio_organization_select.html"
    context_object_name = "portfolio"
    form_class = portfolioForms.PortfolioOrganizationSelectForm
    pk_url_kwarg = "portfolio_pk"

    def get(self, request):
        """
        Prevent user from calling this view directly.
        View already requires a form to change session and verifies user has permission
        to call this on passed portfolio, but added for additional protections.
        """
        return JsonResponse({"error": "You cannot access this page directly"}, status=404)

    def post(self, request):
        """
        Handles updating active portfolio in session.
        """
        self.form = self.get_form()
        portfolio_button = self.form["set_session_portfolio_button"]
        portfolio_name = portfolio_button.value()
        portfolio = Portfolio.objects.get(organization_name=portfolio_name)

        # Verify user has permissions to access selected portfolio
        portfolio_permission = UserPortfolioPermission.objects.filter(portfolio=portfolio, user=request.user).first()
        if not portfolio_permission:
            return JsonResponse({"error": "Invalid user portfolio permission"}, status=403)
        if portfolio_permission.user != request.user:
            return JsonResponse({"error": "User does not have permissions to access this portfolio"}, status=403)

        portfolio = get_object_or_404(Portfolio, pk=portfolio.id)
        request.session["portfolio"] = portfolio
        logger.info(f"Successfully set active portfolio to {portfolio}")
        return self._handle_success_response(request, portfolio)

    def _handle_success_response(self, request, portfolio):
        """
        Return a success response (JSON or redirect with messages).
        """
        success_message = f"You set your active portfolio to {portfolio}."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success_message}, status=200)
        return redirect(reverse("domains"))
