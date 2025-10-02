from datetime import date
import logging
from contextvars import ContextVar
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.generic import DeleteView, DetailView, UpdateView
from django.views.generic.edit import FormMixin
from django.conf import settings
from registrar.utility.errors import APIError, RegistrySystemError
from registrar.decorators import (
    HAS_PORTFOLIO_DOMAINS_VIEW_ALL,
    IS_DOMAIN_MANAGER,
    IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER,
    IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER,
    IS_STAFF,
    IS_STAFF_MANAGING_DOMAIN,
    grant_access,
)
from registrar.forms.domain import DomainSuborganizationForm, DomainRenewalForm
from registrar.models import (
    Domain,
    DomainRequest,
    DomainInformation,
    DomainInvitation,
    PortfolioInvitation,
    UserDomainRole,
    PublicContact,
)
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
from registrar.utility.enums import DefaultEmail
from registrar.utility.errors import (
    GenericError,
    GenericErrorCodes,
    NameserverError,
    NameserverErrorCodes as nsErrorCodes,
    DsDataError,
    DsDataErrorCodes,
    SecurityEmailError,
    SecurityEmailErrorCodes,
)
from registrar.models.utility.contact_error import ContactError
from registrar.utility.waffle import flag_is_active_for_user
from registrar.views.utility.invitation_helper import (
    get_org_membership,
    get_requested_user,
    handle_invitation_exceptions,
)

from registrar.services.dns_host_service import DnsHostService

from ..forms import (
    SeniorOfficialContactForm,
    DomainOrgNameAddressForm,
    DomainAddUserForm,
    DomainSecurityEmailForm,
    NameserverFormset,
    DomainDnssecForm,
    DomainDsdataFormset,
    DomainDsdataForm,
    DomainDeleteForm,
)

from epplibwrapper import (
    common,
    extensions,
    RegistryError,
)

from ..utility.email import send_templated_email, EmailSendingError
from ..utility.email_invitations import (
    send_domain_invitation_email,
    send_domain_manager_removal_emails_to_domain_managers,
    send_portfolio_invitation_email,
)
from django import forms

logger = logging.getLogger(__name__)

context_dns_record = ContextVar("context_dns_record", default=None)


class DomainBaseView(PermissionRequiredMixin, DetailView):
    """
    Base View for the Domain. Handles getting and setting the domain
    in session cache on GETs. Also provides methods for getting
    and setting the domain in cache
    """

    model = Domain
    pk_url_kwarg = "domain_pk"
    context_object_name = "domain"

    def get(self, request, *args, **kwargs):
        self._get_domain(request)
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def _get_domain(self, request):
        """
        get domain from session cache or from db and set
        to self.object
        set session to self for downstream functions to
        update session cache
        """
        self.session = request.session
        # domain:private_key is the session key to use for
        # caching the domain in the session
        domain_pk = "domain:" + str(self.kwargs.get("domain_pk"))
        cached_domain = self.session.get(domain_pk)

        if cached_domain:
            self.object = cached_domain
        else:
            self.object = self.get_object()
        self._update_session_with_domain()

    def _update_session_with_domain(self):
        """
        update domain in the session cache
        """
        domain_pk = "domain:" + str(self.kwargs.get("domain_pk"))
        self.session[domain_pk] = self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["is_analyst_or_superuser"] = user.has_perm("registrar.analyst_access_permission") or user.has_perm(
            "registrar.full_access_permission"
        )
        context["is_domain_manager"] = UserDomainRole.objects.filter(user=user, domain=self.object).exists()
        context["is_portfolio_user"] = self.can_access_domain_via_portfolio(self.object.pk)
        context["is_editable"] = self.is_editable()
        context["domain_deletion"] = flag_is_active_for_user(self.request.user, "domain_deletion")
        # context["display_renewal_form"] = self.display_renewal_form_check()
        # Stored in a variable for the linter
        action = "analyst_action"
        action_location = "analyst_action_location"
        # Flag to see if an analyst is attempting to make edits
        if action in self.request.session:
            context[action] = self.request.session[action]
        if action_location in self.request.session:
            context[action_location] = self.request.session[action_location]

        return context

    def is_editable(self):
        """Returns whether domain is editable in the context of the view"""
        domain_editable = self.object.is_editable()
        if not domain_editable:
            return False

        # if user is domain manager or analyst or admin, return True
        if (
            self.can_access_other_user_domains(self.object.id)
            or UserDomainRole.objects.filter(user=self.request.user, domain=self.object).exists()
        ):
            return True

        return False

    def can_access_domain_via_portfolio(self, pk):
        """Most views should not allow permission to portfolio users.
        If particular views allow access to the domain pages, they will need to override
        this function.
        """
        return False

    def has_permission(self):
        """Check if this user has access to this domain.

        The user is in self.request.user and the domain needs to be looked
        up from the domain's primary key in self.kwargs["domain_pk"]
        """
        pk = self.kwargs["domain_pk"]

        # test if domain in editable state
        if not self.in_editable_state(pk):
            return False

        # if we need to check more about the nature of role, do it here.
        return True

    def in_editable_state(self, pk):
        """Is the domain in an editable state"""
        requested_domain = None
        if Domain.objects.filter(id=pk).exists():
            requested_domain = Domain.objects.get(id=pk)

        # if domain is editable return true
        if requested_domain and requested_domain.is_editable():
            return True
        return False

    def can_access_other_user_domains(self, pk):
        """Checks to see if an authorized user (staff or superuser)
        can access a domain that they did not create or was invited to.
        """

        # Check if the user is permissioned...
        user_is_analyst_or_superuser = self.request.user.has_perm(
            "registrar.analyst_access_permission"
        ) or self.request.user.has_perm("registrar.full_access_permission")

        if not user_is_analyst_or_superuser:
            return False

        # Check if the user is attempting a valid edit action.
        # In other words, if the analyst/admin did not click
        # the 'Manage Domain' button in /admin,
        # then they cannot access this page.
        session = self.request.session
        can_do_action = (
            "analyst_action" in session
            and "analyst_action_location" in session
            and session["analyst_action_location"] == pk
        )

        if not can_do_action:
            return False

        # Analysts may manage domains, when they are in these statuses:
        valid_domain_statuses = [
            DomainRequest.DomainRequestStatus.APPROVED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.REJECTED,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            # Edge case - some domains do not have
            # a status or DomainInformation... aka a status of 'None'.
            # It is necessary to access those to correct errors.
            None,
        ]

        requested_domain = None
        if DomainInformation.objects.filter(id=pk).exists():
            requested_domain = DomainInformation.objects.get(id=pk)

        # if no domain information or domain request exist, the user
        # should be able to manage the domain; however, if domain information
        # and domain request exist, and domain request is not in valid status,
        # user should not be able to manage domain
        if (
            requested_domain
            and requested_domain.domain_request
            and requested_domain.domain_request.status not in valid_domain_statuses
        ):
            return False

        # Valid session keys exist,
        # the user is permissioned,
        # and it is in a valid status
        return True


class DomainFormBaseView(DomainBaseView, FormMixin):
    """
    Form Base View for the Domain. Handles getting and setting
    domain in cache when dealing with domain forms. Provides
    implementations of post, form_valid and form_invalid.
    """

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using DomainBaseView and FormMixin
        """
        self._get_domain(request)
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        # updates session cache with domain
        self._update_session_with_domain()

        # superclass has the redirect
        return super().form_valid(form)

    def form_invalid(self, form):
        # updates session cache with domain
        self._update_session_with_domain()

        # superclass has the redirect
        return super().form_invalid(form)

    def get_domain_info_from_domain(self) -> DomainInformation | None:
        """
        Grabs the underlying domain_info object based off of self.object.name.
        Returns None if nothing is found.
        """
        _domain_info = DomainInformation.objects.filter(domain__name=self.object.name)
        current_domain_info = None
        if _domain_info.exists() and _domain_info.count() == 1:
            current_domain_info = _domain_info.get()
        else:
            logger.error("Could get domain_info. No domain info exists, or duplicates exist.")

        return current_domain_info

    def send_update_notification(self, form, force_send=False):
        """Send a notification to all domain managers that an update has occured
        for a single domain. Uses update_to_approved_domain.txt template.

        If there are no changes to the form, emails will NOT be sent unless force_send
        is set to True.
        """

        # send notification email for changes to any of these forms
        form_label_dict = {
            DomainSecurityEmailForm: "Security email",
            DomainDnssecForm: "DNSSEC / DS Data",
            DomainDsdataFormset: "DNSSEC / DS Data",
            DomainOrgNameAddressForm: "Organization details",
            SeniorOfficialContactForm: "Senior official",
            NameserverFormset: "Name servers",
        }

        # forms of these types should not send notifications if they're part of a portfolio/Organization
        check_for_portfolio = {
            DomainOrgNameAddressForm,
            SeniorOfficialContactForm,
        }

        is_analyst_action = "analyst_action" in self.session and "analyst_action_location" in self.session

        should_notify = False

        if form.__class__ in form_label_dict:
            if is_analyst_action:
                logger.debug("No notification sent: Action was conducted by an analyst")
            else:
                # these types of forms can cause notifications
                should_notify = True
                if form.__class__ in check_for_portfolio:
                    # some forms shouldn't cause notifications if they are in a portfolio
                    info = self.get_domain_info_from_domain()
                    is_org_user = self.request.user.is_org_user(self.request)
                    if is_org_user and (not info or info.portfolio):
                        logger.debug("No notification sent: Domain is part of a portfolio")
                        should_notify = False
        else:
            # don't notify for any other types of forms
            should_notify = False
        if should_notify and (form.has_changed() or force_send):
            context = {
                "domain": self.object.name,
                "user": self.request.user,
                "date": date.today(),
                "changes": form_label_dict[form.__class__],
            }
            self.email_domain_managers(
                self.object,
                "emails/update_to_approved_domain.txt",
                "emails/update_to_approved_domain_subject.txt",
                context,
            )
        else:
            logger.info(f"No notification sent for {form.__class__}.")

    def email_domain_managers(self, domain: Domain, template: str, subject_template: str, context={}):
        """Send a single email built from a template to all managers for a given domain.

        template_name and subject_template_name are relative to the same template
        context as Django's HTML templates. context gives additional information
        that the template may use.

        context is a dictionary containing any information needed to fill in values
        in the provided template, exactly the same as with send_templated_email.

        Will log a warning if the email fails to send for any reason, but will not raise an error.
        """
        manager_roles = UserDomainRole.objects.filter(domain=domain.pk, role=UserDomainRole.Roles.MANAGER)

        for role in manager_roles:
            manager = role.user
            context["recipient"] = manager
            try:
                send_templated_email(template, subject_template, to_addresses=[manager.email], context=context)
            except EmailSendingError as err:
                logger.error(
                    "Failed to send notification email:\n"
                    f"  Subject template: {subject_template}\n"
                    f"  To: {manager.email}\n"
                    f"  Domain: {domain.name}\n"
                    f"  Error: {err}",
                    exc_info=True,
                )


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN, HAS_PORTFOLIO_DOMAINS_VIEW_ALL)
class DomainView(DomainBaseView):
    """Domain detail overview page"""

    template_name = "domain_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        default_emails = DefaultEmail.get_all_emails()

        context["hidden_security_emails"] = default_emails
        context["user_portfolio_permission"] = UserPortfolioPermission.objects.filter(
            user=self.request.user, portfolio=self.request.session.get("portfolio")
        ).first()

        security_email = self.object.get_security_email()
        if security_email is None or security_email in default_emails:
            context["security_email"] = None
            return context
        context["security_email"] = security_email
        return context

    def can_access_domain_via_portfolio(self, pk):
        """Most views should not allow permission to portfolio users.
        If particular views allow permissions, they will need to override
        this function."""
        portfolio = self.request.session.get("portfolio")
        if self.request.user.has_any_domains_portfolio_permission(portfolio):
            if Domain.objects.filter(id=pk).exists():
                domain = Domain.objects.get(id=pk)
                if domain.domain_info.portfolio == portfolio:
                    return True
        return False

    def in_editable_state(self, pk):
        """Override in_editable_state from DomainPermission
        Allow detail page to be viewable"""

        requested_domain = None
        if Domain.objects.filter(id=pk).exists():
            requested_domain = Domain.objects.get(id=pk)

        # return true if the domain exists, this will allow the detail page to load
        if requested_domain:
            return True
        return False

    def _get_domain(self, request):
        """
        override get_domain for this view so that domain overview
        always resets the cache for the domain object
        """
        self.session = request.session
        self.object = self.get_object()
        self._update_session_with_domain()


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainLifecycleView(DomainBaseView):

    template_name = "domain_lifecycle.html"

    def get_context_data(self, **kwargs):
        """Adds custom context."""
        context = super().get_context_data(**kwargs)
        return context


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainRenewalView(DomainBaseView):
    """Domain detail overview page."""

    template_name = "domain_renewal.html"

    def get_context_data(self, **kwargs):
        """Grabs the security email information and adds security_email to the renewal form context
        sets it to None if it uses a default email"""

        context = super().get_context_data(**kwargs)

        default_emails = DefaultEmail.get_all_emails()

        context["hidden_security_emails"] = default_emails

        security_email = self.object.get_security_email()
        context["security_email"] = security_email
        return context

    def in_editable_state(self, pk):
        """Override in_editable_state from DomainPermission
        Allow renewal form to be accessed
        returns boolean"""
        requested_domain = None
        if Domain.objects.filter(id=pk).exists():
            requested_domain = Domain.objects.get(id=pk)

        return (
            requested_domain
            and requested_domain.is_editable()
            and (requested_domain.is_expiring() or requested_domain.is_expired())
        )

    def post(self, request, domain_pk):

        domain = get_object_or_404(Domain, id=domain_pk)

        form = DomainRenewalForm(request.POST)

        if form.is_valid():

            # check for key in the post request data
            if "submit_button" in request.POST:
                try:
                    domain.renew_domain()
                    messages.success(request, "This domain has been renewed for one year.")
                except Exception:
                    messages.error(
                        request,
                        "This domain has not been renewed for one year, "
                        "please email help@get.gov if this problem persists.",
                    )
            return HttpResponseRedirect(reverse("domain", kwargs={"domain_pk": domain_pk}))

        # if not valid, render the template with error messages
        # passing editable and is_editable for re-render
        return render(
            request,
            "domain_renewal.html",
            {
                "domain": domain,
                "form": form,
                "is_editable": True,
                "is_domain_manager": True,
            },
        )


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainDeleteView(DomainFormBaseView):
    """Domain delete page."""

    template_name = "domain_delete.html"
    form_class = DomainDeleteForm

    def post(self, request, domain_pk):
        domain = get_object_or_404(Domain, pk=domain_pk)
        self.object = domain
        form = self.form_class(request.POST)
        is_policy_acknowledged = request.POST.get("is_policy_acknowledged", "False") == "True"

        if form.is_valid():
            if domain.state != "ready":
                messages.error(request, f"Cannot delete domain {domain.name} from current state {domain.state}.")
                return self.render_to_response(self.get_context_data(form=form))
            if is_policy_acknowledged:
                domain.place_client_hold()
                domain.save()
                messages.success(request, f"The domain '{domain.name}' was deleted successfully.")
                # redirect to domain overview
                return redirect(reverse("domain", kwargs={"domain_pk": domain.pk}))
            return self.render_to_response(self.get_context_data(form=form))

        # Form not valid -> redisplay with errors
        return self.render_to_response(self.get_context_data(form=form))


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainOrgNameAddressView(DomainFormBaseView):
    """Organization view"""

    model = Domain
    template_name = "domain_org_name_address.html"
    context_object_name = "domain"
    form_class = DomainOrgNameAddressForm

    def get_form_kwargs(self, *args, **kwargs):
        """Add domain_info.organization_name instance to make a bound form."""
        form_kwargs = super().get_form_kwargs(*args, **kwargs)
        form_kwargs["instance"] = self.object.domain_info
        return form_kwargs

    def get_success_url(self):
        """Redirect to the overview page for the domain."""
        return reverse("domain-org-name-address", kwargs={"domain_pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, save the organization name and mailing address."""
        self.send_update_notification(form)

        form.save()

        messages.success(self.request, "The organization information for this domain has been updated.")

        # superclass has the redirect
        return super().form_valid(form)

    def has_permission(self):
        """Override for the has_permission class to exclude portfolio users"""

        # Org users shouldn't have access to this page
        is_org_user = self.request.user.is_org_user(self.request)
        portfolio = self.request.session.get("portfolio")
        if portfolio and is_org_user:
            return False
        else:
            return super().has_permission()


@grant_access(IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainSubOrganizationView(DomainFormBaseView):
    """Suborganization view"""

    model = Domain
    template_name = "domain_suborganization.html"
    context_object_name = "domain"
    form_class = DomainSuborganizationForm

    def has_permission(self):
        """Override for the has_permission class to exclude non-portfolio users"""

        # non-org users shouldn't have access to this page
        is_org_user = self.request.user.is_org_user(self.request)
        portfolio = self.request.session.get("portfolio")
        if portfolio and is_org_user:
            return super().has_permission()
        else:
            return False

    def get_context_data(self, **kwargs):
        """Adds custom context."""
        context = super().get_context_data(**kwargs)
        if self.object and self.object.domain_info and self.object.domain_info.sub_organization:
            context["suborganization_name"] = self.object.domain_info.sub_organization.name
        return context

    def get_form_kwargs(self, *args, **kwargs):
        """Add domain_info.organization_name instance to make a bound form."""
        form_kwargs = super().get_form_kwargs(*args, **kwargs)
        form_kwargs["instance"] = self.object.domain_info
        return form_kwargs

    def get_success_url(self):
        """Redirect to the overview page for the domain."""
        return reverse("domain-suborganization", kwargs={"domain_pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, save the organization name and mailing address."""
        form.save()

        messages.success(self.request, "The suborganization name for this domain has been updated.")

        # superclass has the redirect
        return super().form_valid(form)


@grant_access(IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER, IS_STAFF_MANAGING_DOMAIN)
class DomainSeniorOfficialView(DomainFormBaseView):
    """Domain senior official editing view."""

    model = Domain
    template_name = "domain_senior_official.html"
    context_object_name = "domain"
    form_class = SeniorOfficialContactForm

    def get_form_kwargs(self, *args, **kwargs):
        """Add domain_info.senior_official instance to make a bound form."""
        form_kwargs = super().get_form_kwargs(*args, **kwargs)
        form_kwargs["instance"] = self.object.domain_info.senior_official

        domain_info = self.get_domain_info_from_domain()
        invalid_fields = [DomainRequest.OrganizationChoices.FEDERAL, DomainRequest.OrganizationChoices.TRIBAL]
        is_federal_or_tribal = domain_info and (domain_info.generic_org_type in invalid_fields)
        form_kwargs["disable_fields"] = is_federal_or_tribal
        return form_kwargs

    def get_context_data(self, **kwargs):
        """Adds custom context."""
        context = super().get_context_data(**kwargs)
        context["generic_org_type"] = self.object.domain_info.generic_org_type
        return context

    def get_success_url(self):
        """Redirect to the overview page for the domain."""
        return reverse("domain-senior-official", kwargs={"domain_pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, save the senior official."""

        # Set the domain information in the form so that it can be accessible
        # to associate a new Contact, if a new Contact is needed
        # in the save() method
        form.set_domain_info(self.object.domain_info)
        form.save()

        self.send_update_notification(form)

        messages.success(self.request, "The senior official for this domain has been updated.")

        # superclass has the redirect
        return super().form_valid(form)

    def has_permission(self):
        """Override for the has_permission class to exclude portfolio users"""

        # Org users shouldn't have access to this page
        is_org_user = self.request.user.is_org_user(self.request)
        portfolio = self.request.session.get("portfolio")
        if portfolio and is_org_user:
            return False
        else:
            return super().has_permission()


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainDNSView(DomainBaseView):
    """DNS Information View."""

    template_name = "domain_dns.html"
    valid_domains = ["igorville.gov", "domainops.gov"]

    def get_context_data(self, **kwargs):
        """Adds custom context."""
        context = super().get_context_data(**kwargs)
        context["dns_prototype_flag"] = flag_is_active_for_user(self.request.user, "dns_prototype_flag")
        context["is_valid_domain"] = self.object.name in self.valid_domains
        return context


class PrototypeDomainDNSRecordForm(forms.Form):
    """Form for adding DNS records in prototype."""

    name = forms.CharField(label="DNS record name (A record)", required=True, help_text="DNS record name")

    content = forms.GenericIPAddressField(
        label="IPv4 Address",
        required=True,
        protocol="IPv4",
    )

    ttl = forms.ChoiceField(
        label="TTL",
        choices=[
            (1, "Automatic"),
            (60, "1 minute"),
            (300, "5 minutes"),
            (1800, "30 minutes"),
            (3600, "1 hour"),
            (7200, "2 hours"),
            (18000, "5 hours"),
            (43200, "12 hours"),
            (86400, "1 day"),
        ],
        initial=1,
    )


@grant_access(IS_STAFF)
class PrototypeDomainDNSRecordView(DomainFormBaseView):
    template_name = "prototype_domain_dns.html"
    form_class = PrototypeDomainDNSRecordForm
    valid_domains = ["igorville.gov", "domainops.gov", "dns.gov"]
    dns_host_service = DnsHostService()

    def __init__(self):
        self.dns_record = None

    def get_context_data(self, **kwargs):
        """Adds custom context."""
        context = super().get_context_data(**kwargs)
        context["dns_record"] = context_dns_record.get()
        return context

    def has_permission(self):
        has_permission = super().has_permission()
        if not has_permission:
            return False

        flag_enabled = flag_is_active_for_user(self.request.user, "dns_prototype_flag")
        if not flag_enabled:
            return False

        self.object = self.get_object()
        if self.object.name not in self.valid_domains:
            return False

        return True

    def get_success_url(self):
        return reverse("prototype-domain-dns", kwargs={"domain_pk": self.object.pk})

    def find_by_name(self, items, name):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("id") for item in items if item.get("name") == name), None)

    def post(self, request, *args, **kwargs):  # noqa: C901
        """Handle form submission."""
        self.object = self.get_object()
        form = self.get_form()
        errors = []
        if form.is_valid():
            try:
                if settings.IS_PRODUCTION and self.object.name != "igorville.gov":
                    raise Exception(f"create dns record was called for domain {self.name}")

                if not settings.IS_PRODUCTION and self.object.name not in self.valid_domains:
                    raise Exception(
                        f"Can only create DNS records for: {self.valid_domains}."
                        " Create one in a test environment if it doesn't already exist."
                    )

                record_data = {
                    "type": "A",
                    "name": form.cleaned_data["name"],  # record name
                    "content": form.cleaned_data["content"],  # IPv4
                    "ttl": int(form.cleaned_data["ttl"]),
                    "comment": "Test record",
                }

                account_name = f"account-{self.object.name}"
                zone_name = f"{self.object.name}"  # must be a domain name
                zone_id = ""

                try:
                    _, zone_id, nameservers = self.dns_host_service.dns_setup(account_name, zone_name)
                except APIError as e:
                    logger.error(f"API error in view: {str(e)}")

                if zone_id:
                    # post nameservers to registry
                    try:
                        self._register_nameservers(zone_name, nameservers)
                    except RegistrySystemError as e:
                        logger.error(f"Unable to register nameservers {e}")

                    try:
                        record_response = self.dns_host_service.create_record(zone_id, record_data)
                        logger.info(f"Created DNS record: {record_response['result']}")
                        self.dns_record = record_response["result"]
                        dns_name = record_response["result"]["name"]
                        messages.success(request, f"DNS A record '{dns_name}' created successfully.")
                    except APIError as e:
                        logger.error(f"API error in view: {str(e)}")

                context_dns_record.set(self.dns_record)
            finally:
                if errors:
                    messages.error(request, f"Request errors: {errors}")
        return super().post(request)


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainNameserversView(DomainFormBaseView):
    """Domain nameserver editing view."""

    template_name = "domain_nameservers.html"
    form_class = NameserverFormset
    model = Domain

    def get_initial(self):
        """The initial value for the form (which is a formset here)."""
        nameservers = self.object.nameservers
        initial_data = []
        if nameservers is not None:
            # Add existing nameservers as initial data
            initial_data.extend({"server": name, "ip": ",".join(ip)} for name, ip in nameservers)

        # Ensure 2 fields in the case we have no data
        if len(initial_data) == 0:
            initial_data.append({})

        return initial_data

    def get_success_url(self):
        """Redirect to the nameservers page for the domain."""
        return reverse("domain-dns-nameservers", kwargs={"domain_pk": self.object.pk})

    def get_context_data(self, **kwargs):
        """Adjust context from FormMixin for formsets."""
        context = super().get_context_data(**kwargs)
        # use "formset" instead of "form" for the key
        context["formset"] = context.pop("form")
        return context

    def get_form(self, **kwargs):
        """Override the labels and required fields every time we get a formset."""
        formset = super().get_form(**kwargs)

        for i, form in enumerate(formset):
            form.fields["server"].label += f" {i+1}"
            form.fields["domain"].initial = self.object.name
        return formset

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using DomainBaseView and FormMixin
        """
        self._get_domain(request)
        formset = self.get_form()

        if "btn-cancel-click" in request.POST:
            url = self.get_success_url()
            return HttpResponseRedirect(url)

        if formset.is_valid():
            logger.debug("formset is valid")
            return self.form_valid(formset)
        else:
            logger.debug("formset is invalid")
            logger.debug(formset.errors)
            return self.form_invalid(formset)

    def form_valid(self, formset):
        """The formset is valid, perform something with it."""

        self.request.session["nameservers_form_domain"] = self.object
        initial_state = self.object.state

        # Set the nameservers from the formset
        nameservers = []
        for form in formset:
            try:
                ip_string = form.cleaned_data["ip"]
                # ip_string will be None or a string of IP addresses
                # comma-separated
                ip_list = []
                if ip_string:
                    # Split the string into a list using a comma as the delimiter
                    ip_list = ip_string.split(",")

                as_tuple = (
                    form.cleaned_data["server"],
                    ip_list,
                )
                nameservers.append(as_tuple)
            except KeyError:
                # no server information in this field, skip it
                pass
        try:
            self.object.nameservers = nameservers
        except NameserverError as Err:
            # NamserverErrors *should* be caught in form; if reached here,
            # there was an uncaught error in submission (through EPP)
            messages.error(self.request, NameserverError(code=nsErrorCodes.BAD_DATA))
            logger.error(f"Nameservers error: {Err}")
        # TODO: registry is not throwing an error when no connection
        except RegistryError as Err:
            if Err.is_connection_error():
                messages.error(
                    self.request,
                    GenericError(code=GenericErrorCodes.CANNOT_CONTACT_REGISTRY),
                )
                logger.error(f"Registry connection error: {Err}")
            else:
                messages.error(self.request, NameserverError(code=nsErrorCodes.BAD_DATA))
                logger.error(f"Registry error: {Err}")
        else:
            if initial_state == Domain.State.READY:
                self.send_update_notification(formset)
            messages.success(
                self.request,
                "The name servers for this domain have been updated. "
                "Note that DNS changes could take anywhere from a few minutes to "
                "48 hours to propagate across the internet.",
            )

        # superclass has the redirect
        return super().form_valid(formset)


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainDNSSECView(DomainFormBaseView):
    """Domain DNSSEC editing view."""

    template_name = "domain_dnssec.html"
    form_class = DomainDnssecForm

    def get_context_data(self, **kwargs):
        """The initial value for the form (which is a formset here)."""
        context = super().get_context_data(**kwargs)

        has_dnssec_records = self.object.dnssecdata is not None
        context["has_dnssec_records"] = has_dnssec_records
        context["dnssec_enabled"] = self.request.session.pop("dnssec_enabled", False)

        return context

    def get_success_url(self):
        """Redirect to the DNSSEC page for the domain."""
        return reverse("domain-dns-dnssec", kwargs={"domain_pk": self.object.pk})

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view."""
        self._get_domain(request)
        form = self.get_form()
        if form.is_valid():
            if "disable_dnssec" in request.POST:
                try:
                    self.object.dnssecdata = {}
                except RegistryError as err:
                    errmsg = "Error removing existing DNSSEC record(s)."
                    logger.error(errmsg + ": " + err)
                    messages.error(self.request, errmsg)
                else:
                    self.send_update_notification(form, force_send=True)
        return self.form_valid(form)


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainDsDataView(DomainFormBaseView):
    """Domain DNSSEC ds data editing view."""

    template_name = "domain_dsdata.html"
    form_class = DomainDsdataFormset
    form = DomainDsdataForm

    def get_initial(self):
        """The initial value for the form (which is a formset here)."""
        dnssecdata: extensions.DNSSECExtension = self.object.dnssecdata
        initial_data = []

        if dnssecdata is not None and dnssecdata.dsData is not None:
            # Add existing nameservers as initial data
            initial_data.extend(
                {
                    "key_tag": record.keyTag,
                    "algorithm": record.alg,
                    "digest_type": record.digestType,
                    "digest": record.digest,
                }
                for record in dnssecdata.dsData
            )

        return initial_data

    def get_success_url(self):
        """Redirect to the DS data page for the domain."""
        return reverse("domain-dns-dnssec-dsdata", kwargs={"domain_pk": self.object.pk})

    def get_context_data(self, **kwargs):
        """Adjust context from FormMixin for formsets."""
        context = super().get_context_data(**kwargs)
        # use "formset" instead of "form" for the key
        context["formset"] = context.pop("form")

        return context

    def post(self, request, *args, **kwargs):
        """Formset submission posts to this view."""
        self._get_domain(request)
        formset = self.get_form()

        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset, **kwargs):
        """The formset is valid, perform something with it."""

        # Set the dnssecdata from the formset
        dnssecdata = extensions.DNSSECExtension()

        for form in formset:
            if form.cleaned_data.get("DELETE"):  # Check if form is marked for deletion
                continue  # Skip processing this form

            try:
                dsrecord = {
                    "keyTag": int(form.cleaned_data["key_tag"]),
                    "alg": int(form.cleaned_data["algorithm"]),
                    "digestType": int(form.cleaned_data["digest_type"]),
                    "digest": form.cleaned_data["digest"],
                }
                if dnssecdata.dsData is None:
                    dnssecdata.dsData = []
                dnssecdata.dsData.append(common.DSData(**dsrecord))
            except KeyError:
                # no cleaned_data provided for this form, but passed
                # as valid; this can happen if form has been added but
                # not been interacted with; in that case, want to ignore
                pass
        try:
            self.object.dnssecdata = dnssecdata
        except RegistryError as err:
            if err.is_connection_error():
                messages.error(
                    self.request,
                    GenericError(code=GenericErrorCodes.CANNOT_CONTACT_REGISTRY),
                )
                logger.error(f"Registry connection error: {err}")
            else:
                messages.error(self.request, DsDataError(code=DsDataErrorCodes.BAD_DATA))
                logger.error(f"Registry error: {err}")
            return self.form_invalid(formset)
        else:
            self.send_update_notification(formset)

            messages.success(self.request, "The DS data records for this domain have been updated.")
            # superclass has the redirect
            return super().form_valid(formset)


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainSecurityEmailView(DomainFormBaseView):
    """Domain security email editing view."""

    template_name = "domain_security_email.html"
    form_class = DomainSecurityEmailForm

    def get_initial(self):
        """The initial value for the form."""
        initial = super().get_initial()
        security_contact = self.object.security_contact

        invalid_emails = DefaultEmail.get_all_emails()
        if security_contact is None or security_contact.email in invalid_emails:
            initial["security_email"] = None
            return initial
        initial["security_email"] = security_contact.email
        return initial

    def get_success_url(self):
        """Redirect to the security email page for the domain."""
        return reverse("domain-security-email", kwargs={"domain_pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, call setter in model."""

        # Set the security email from the form
        new_email: str = form.cleaned_data.get("security_email", "")

        # If we pass nothing for the sec email, set to the default
        if new_email is None or new_email.strip() == "":
            new_email = PublicContact.get_default_security().email

        contact = self.object.security_contact

        # If no default is created for security_contact,
        # then we cannot connect to the registry.
        if contact is None:
            messages.error(
                self.request,
                GenericError(code=GenericErrorCodes.CANNOT_CONTACT_REGISTRY),
            )
            return redirect(self.get_success_url())

        contact.email = new_email

        try:
            contact.save()
        except RegistryError as Err:
            if Err.is_connection_error():
                messages.error(
                    self.request,
                    GenericError(code=GenericErrorCodes.CANNOT_CONTACT_REGISTRY),
                )
                logger.error(f"Registry connection error: {Err}")
            else:
                messages.error(self.request, SecurityEmailError(code=SecurityEmailErrorCodes.BAD_DATA))
                logger.error(f"Registry error: {Err}")
        except ContactError as Err:
            messages.error(self.request, SecurityEmailError(code=SecurityEmailErrorCodes.BAD_DATA))
            logger.error(f"Generic registry error: {Err}")
        else:
            self.send_update_notification(form)
            messages.success(self.request, "The security email for this domain has been updated.")

            # superclass has the redirect
            return super().form_valid(form)

        # superclass has the redirect
        return redirect(self.get_success_url())


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainUsersView(DomainBaseView):
    """Domain managers page in the domain details."""

    template_name = "domain_users.html"

    def get_context_data(self, **kwargs):
        """The initial value for the form (which is a formset here)."""
        context = super().get_context_data(**kwargs)

        # Get portfolio from session (if set)
        portfolio = self.request.session.get("portfolio")

        # Add domain manager roles separately in order to also pass admin status
        context = self._add_domain_manager_roles_to_context(context, portfolio)

        # Add domain invitations separately in order to also pass admin status
        context = self._add_invitations_to_context(context, portfolio)

        # Get the email of the current user
        context["current_user_email"] = self.request.user.email

        return context

    def _add_domain_manager_roles_to_context(self, context, portfolio):
        """Add domain_manager_roles to context separately, as roles need admin indicator."""

        # Prepare a list to store roles with an admin flag
        domain_manager_roles = []

        for permission in self.object.permissions.all():
            # Determine if the user has the ORGANIZATION_ADMIN role
            has_admin_flag = any(
                UserPortfolioRoleChoices.ORGANIZATION_ADMIN in portfolio_permission.roles
                and portfolio == portfolio_permission.portfolio
                for portfolio_permission in permission.user.portfolio_permissions.all()
            )

            # Add the role along with the computed flag to the list
            domain_manager_roles.append({"permission": permission, "has_admin_flag": has_admin_flag})

        # Pass roles_with_flags to the context
        context["domain_manager_roles"] = domain_manager_roles

        return context

    def _add_invitations_to_context(self, context, portfolio):
        """Add invitations to context separately as invitations needs admin indicator."""

        # Prepare a list to store invitations with an admin flag
        invitations = []

        for domain_invitation in self.object.invitations.all():
            # Check if there are any PortfolioInvitations linked to the same portfolio with the ORGANIZATION_ADMIN role
            has_admin_flag = False

            # Query PortfolioInvitations linked to the same portfolio and check roles
            portfolio_invitations = PortfolioInvitation.objects.filter(
                portfolio=portfolio, email=domain_invitation.email
            )

            # If any of the PortfolioInvitations have the ORGANIZATION_ADMIN role, set the flag to True
            for portfolio_invitation in portfolio_invitations:
                if (
                    portfolio_invitation.roles
                    and UserPortfolioRoleChoices.ORGANIZATION_ADMIN in portfolio_invitation.roles
                ):
                    has_admin_flag = True
                    break  # Once we find one match, no need to check further

            # Add the role along with the computed flag to the list if the domain invitation
            # if the status is not canceled
            if domain_invitation.status != "canceled":
                invitations.append({"domain_invitation": domain_invitation, "has_admin_flag": has_admin_flag})

        # Pass roles_with_flags to the context
        context["invitations"] = invitations

        return context


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainAddUserView(DomainFormBaseView):
    """Inside of a domain's user management, a form for adding users.

    Multiple inheritance is used here for permissions, form handling, and
    details of the individual domain.
    """

    template_name = "domain_add_user.html"
    form_class = DomainAddUserForm

    def get_success_url(self):
        return reverse("domain-users", kwargs={"domain_pk": self.object.pk})

    def form_valid(self, form):
        """Add the specified user to this domain."""
        requested_email = form.cleaned_data["email"]
        requestor = self.request.user

        # Look up a user with that email
        requested_user = get_requested_user(requested_email)
        # NOTE: This does not account for multiple portfolios flag being set to True
        domain_org = self.object.domain_info.portfolio

        # requestor can only send portfolio invitations if they are staff or if they are a member
        # of the domain's portfolio
        requestor_can_update_portfolio = (
            UserPortfolioPermission.objects.filter(user=requestor, portfolio=domain_org).first() is not None
            or requestor.is_staff
        )

        member_of_a_different_org, member_of_this_org = get_org_membership(domain_org, requested_email, requested_user)
        try:
            # COMMENT: this code does not take into account multiple portfolios flag being set to TRUE

            # determine portfolio of the domain (code currently is looking at requestor's portfolio)
            # if requested_email/user is not member or invited member of this portfolio
            #   send portfolio invitation email
            #   create portfolio invitation
            #   create message to view
            is_org_user = self.request.user.is_org_user(self.request)
            if (
                is_org_user
                and not flag_is_active_for_user(requestor, "multiple_portfolios")
                and domain_org is not None
                and requestor_can_update_portfolio
                and not member_of_this_org
            ):
                send_portfolio_invitation_email(
                    email=requested_email, requestor=requestor, portfolio=domain_org, is_admin_invitation=False
                )
                portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(
                    email=requested_email, portfolio=domain_org, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
                )
                # if user exists for email, immediately retrieve portfolio invitation upon creation
                if requested_user is not None:
                    portfolio_invitation.retrieve()
                    portfolio_invitation.save()
                messages.success(self.request, f"{requested_email} has been invited to the organization: {domain_org}")

            if requested_user is None:
                self._handle_new_user_invitation(requested_email, requestor, member_of_a_different_org)
            else:
                self._handle_existing_user(requested_email, requestor, requested_user, member_of_a_different_org)
        except Exception as e:
            handle_invitation_exceptions(self.request, e, requested_email)

        return redirect(self.get_success_url())

    def _handle_new_user_invitation(self, email, requestor, member_of_different_org):
        """Handle invitation for a new user who does not exist in the system."""
        if not send_domain_invitation_email(
            email=email,
            requestor=requestor,
            domains=self.object,
            is_member_of_different_org=member_of_different_org,
        ):
            messages.warning(self.request, "Could not send email confirmation to existing domain managers.")
        DomainInvitation.objects.get_or_create(email=email, domain=self.object)
        messages.success(self.request, f"{email} has been invited to the domain: {self.object}")

    def _handle_existing_user(self, email, requestor, requested_user, member_of_different_org):
        """Handle adding an existing user to the domain."""
        if not send_domain_invitation_email(
            email=email,
            requestor=requestor,
            domains=self.object,
            is_member_of_different_org=member_of_different_org,
            requested_user=requested_user,
        ):
            messages.warning(self.request, "Could not send email confirmation to existing domain managers.")
        UserDomainRole.objects.create(
            user=requested_user,
            domain=self.object,
            role=UserDomainRole.Roles.MANAGER,
        )
        messages.success(self.request, f"Added user {email}.")


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainInvitationCancelView(SuccessMessageMixin, UpdateView):
    model = DomainInvitation
    pk_url_kwarg = "domain_invitation_pk"
    fields = []

    def post(self, request, *args, **kwargs):
        """Override post method in order to error in the case when the
        domain invitation status is RETRIEVED"""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid() and self.object.status == self.object.DomainInvitationStatus.INVITED:
            self.object.cancel_invitation()
            self.object.save()
            return self.form_valid(form)
        else:
            # Produce an error message if the domain invatation status is RETRIEVED
            messages.error(request, f"Invitation to {self.object.email} has already been retrieved.")
            return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("domain-users", kwargs={"domain_pk": self.object.domain.id})

    def get_success_message(self, cleaned_data):
        return f"Canceled invitation to {self.object.email}."


@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainDeleteUserView(DeleteView):
    """Inside of a domain's user management, a form for deleting users."""

    object: UserDomainRole
    model = UserDomainRole
    context_object_name = "userdomainrole"

    def get_object(self, queryset=None):
        """Custom get_object definition to grab a UserDomainRole object from a domain_id and user_id"""
        domain_id = self.kwargs.get("domain_pk")
        user_id = self.kwargs.get("user_pk")
        return UserDomainRole.objects.get(domain=domain_id, user=user_id)

    def get_success_url(self):
        """Refreshes the page after a delete is successful"""
        return reverse("domain-users", kwargs={"domain_pk": self.object.domain.id})

    def get_success_message(self):
        """Returns confirmation content for the deletion event"""

        # Grab the text representation of the user we want to delete
        email_or_name = self.object.user.email
        if email_or_name is None or email_or_name.strip() == "":
            email_or_name = self.object.user

        # If the user is deleting themselves, return a specific message.
        # If not, return something more generic.
        if self.delete_self:
            message = f"You are no longer managing the domain {self.object.domain}."
        else:
            message = f"Removed {email_or_name} as a manager for this domain."

        return message

    def form_valid(self, form):
        """Delete the specified user on this domain."""

        # Delete the object
        super().form_valid(form)

        # Email all domain managers that domain manager has been removed
        send_domain_manager_removal_emails_to_domain_managers(
            removed_by_user=self.request.user,
            manager_removed=self.object.user,
            manager_removed_email=self.object.user.email,
            domain=self.object.domain,
        )

        # Add a success message
        messages.success(self.request, self.get_success_message())
        return redirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        """Custom post implementation to ensure last userdomainrole is not removed and to
        redirect to home in the event that the user deletes themselves"""
        self.object = self.get_object()  # Retrieve the UserDomainRole to delete

        # Is the user deleting themselves?
        self.delete_self = self.request.user == self.object.user

        # Check if this is the only UserDomainRole for the domain
        if not len(UserDomainRole.objects.filter(domain=self.object.domain)) > 1:
            if self.delete_self:
                messages.error(
                    request,
                    "Domains must have at least one domain manager. "
                    "To remove yourself, the domain needs another domain manager.",
                )
            else:
                messages.error(request, "Domains must have at least one domain manager.")
            return redirect(self.get_success_url())

        # normal delete processing in the event that the above condition not reached
        response = super().post(request, *args, **kwargs)

        # If the user is deleting themselves, redirect to home
        if self.delete_self:
            return redirect(reverse("home"))

        return response
