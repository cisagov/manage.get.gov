"""Views for a single Domain.

Authorization is handled by the `DomainPermissionView`. To ensure that only
authorized users can see information on a domain, every view here should
inherit from `DomainPermissionView` (or DomainInvitationPermissionCancelView).
"""

from datetime import date
import logging
import requests
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.generic.edit import FormMixin
from django.conf import settings
from registrar.forms.domain import DomainSuborganizationForm, DomainRenewalForm
from registrar.models import (
    Domain,
    DomainRequest,
    DomainInformation,
    DomainInvitation,
    PortfolioInvitation,
    User,
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
from registrar.views.utility.permission_views import UserDomainRolePermissionDeleteView
from registrar.utility.waffle import flag_is_active_for_user
from registrar.views.utility.invitation_helper import (
    get_org_membership,
    get_requested_user,
    handle_invitation_exceptions,
)

from ..forms import (
    SeniorOfficialContactForm,
    DomainOrgNameAddressForm,
    DomainAddUserForm,
    DomainSecurityEmailForm,
    NameserverFormset,
    DomainDnssecForm,
    DomainDsdataFormset,
    DomainDsdataForm,
)

from epplibwrapper import (
    common,
    extensions,
    RegistryError,
)

from ..utility.email import send_templated_email, EmailSendingError
from ..utility.email_invitations import send_domain_invitation_email, send_portfolio_invitation_email
from .utility import DomainPermissionView, DomainInvitationPermissionCancelView
from django import forms

logger = logging.getLogger(__name__)


class DomainBaseView(DomainPermissionView):
    """
    Base View for the Domain. Handles getting and setting the domain
    in session cache on GETs. Also provides methods for getting
    and setting the domain in cache
    """

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
        domain_pk = "domain:" + str(self.kwargs.get("pk"))
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
        domain_pk = "domain:" + str(self.kwargs.get("pk"))
        self.session[domain_pk] = self.object


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
                    if not info or info.portfolio:
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
        manager_pks = UserDomainRole.objects.filter(domain=domain.pk, role=UserDomainRole.Roles.MANAGER).values_list(
            "user", flat=True
        )
        emails = list(User.objects.filter(pk__in=manager_pks).values_list("email", flat=True))
        try:
            # Remove the current user so they aren't CC'ed, since they will be the "to_address"
            emails.remove(self.request.user.email)  # type: ignore
        except ValueError:
            pass

        try:
            send_templated_email(
                template,
                subject_template,
                to_address=self.request.user.email,  # type: ignore
                context=context,
                cc_addresses=emails,
            )
        except EmailSendingError:
            logger.warning(
                "Could not sent notification email to %s for domain %s",
                emails,
                domain.name,
                exc_info=True,
            )


class DomainView(DomainBaseView):
    """Domain detail overview page."""

    template_name = "domain_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        default_emails = [DefaultEmail.PUBLIC_CONTACT_DEFAULT.value, DefaultEmail.LEGACY_DEFAULT.value]

        context["hidden_security_emails"] = default_emails

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


class DomainRenewalView(DomainView):
    """Domain detail overview page."""

    template_name = "domain_renewal.html"

    def post(self, request, pk):

        domain = get_object_or_404(Domain, id=pk)

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
            return HttpResponseRedirect(reverse("domain", kwargs={"pk": pk}))

        # if not valid, render the template with error messages
        # passing editable, has_domain_renewal_flag, and is_editable for re-render
        return render(
            request,
            "domain_renewal.html",
            {
                "domain": domain,
                "form": form,
                "is_editable": True,
                "has_domain_renewal_flag": True,
                "is_domain_manager": True,
            },
        )


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
        return reverse("domain-org-name-address", kwargs={"pk": self.object.pk})

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
        return reverse("domain-suborganization", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, save the organization name and mailing address."""
        form.save()

        messages.success(self.request, "The suborganization name for this domain has been updated.")

        # superclass has the redirect
        return super().form_valid(form)


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
        return reverse("domain-senior-official", kwargs={"pk": self.object.pk})

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


class DomainDNSView(DomainBaseView):
    """DNS Information View."""

    template_name = "domain_dns.html"
    valid_domains = ["igorville.gov", "domainops.gov", "dns.gov"]

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


class PrototypeDomainDNSRecordView(DomainFormBaseView):
    template_name = "prototype_domain_dns.html"
    form_class = PrototypeDomainDNSRecordForm
    valid_domains = ["igorville.gov", "domainops.gov", "dns.gov"]

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
        return reverse("prototype-domain-dns", kwargs={"pk": self.object.pk})

    def find_by_name(self, items, name):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("id") for item in items if item.get("name") == name), None)

    def post(self, request, *args, **kwargs):
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

                base_url = "https://api.cloudflare.com/client/v4"
                headers = {
                    "X-Auth-Email": settings.SECRET_REGISTRY_SERVICE_EMAIL,
                    "X-Auth-Key": settings.SECRET_REGISTRY_TENANT_KEY,
                    "Content-Type": "application/json",
                }
                params = {"tenant_name": settings.SECRET_REGISTRY_TENANT_NAME}

                # 1. Get tenant details
                tenant_response = requests.get(f"{base_url}/user/tenants", headers=headers, params=params, timeout=5)
                tenant_response_json = tenant_response.json()
                logger.info(f"Found tenant: {tenant_response_json}")
                tenant_id = tenant_response_json["result"][0]["tenant_tag"]
                errors = tenant_response_json.get("errors", [])
                tenant_response.raise_for_status()

                # 2. Create or get a account under tenant

                # Check to see if the account already exists. Filters accounts by tenant_id / account_name.
                account_name = f"account-{self.object.name}"
                params = {"tenant_id": tenant_id, "name": account_name}

                account_response = requests.get(f"{base_url}/accounts", headers=headers, params=params, timeout=5)
                account_response_json = account_response.json()
                logger.debug(f"account get: {account_response_json}")
                errors = account_response_json.get("errors", [])
                account_response.raise_for_status()

                # See if we already made an account.
                # This maybe doesn't need to be a for loop (1 record or 0) but alas, here we are
                accounts = account_response_json.get("result", [])
                account_id = self.find_by_name(accounts, account_name)

                # If we didn't, create one
                if not account_id:
                    account_response = requests.post(
                        f"{base_url}/accounts",
                        headers=headers,
                        json={"name": account_name, "type": "enterprise", "unit": {"id": tenant_id}},
                        timeout=5,
                    )
                    account_response_json = account_response.json()
                    logger.info(f"Created account: {account_response_json}")
                    account_id = account_response_json["result"]["id"]
                    errors = account_response_json.get("errors", [])
                    account_response.raise_for_status()

                # 3. Create or get a zone under account

                # Try to find an existing zone first by searching on the current id
                zone_name = self.object.name
                params = {"account.id": account_id, "name": zone_name}
                zone_response = requests.get(f"{base_url}/zones", headers=headers, params=params, timeout=5)
                zone_response_json = zone_response.json()
                logger.debug(f"get zone: {zone_response_json}")
                errors = zone_response_json.get("errors", [])
                zone_response.raise_for_status()

                # Get the zone id
                zones = zone_response_json.get("result", [])
                zone_id = self.find_by_name(zones, zone_name)

                # Create one if it doesn't presently exist
                if not zone_id:
                    zone_response = requests.post(
                        f"{base_url}/zones",
                        headers=headers,
                        json={"name": zone_name, "account": {"id": account_id}, "type": "full"},
                        timeout=5,
                    )
                    zone_response_json = zone_response.json()
                    logger.info(f"Created zone: {zone_response_json}")
                    zone_id = zone_response_json.get("result", {}).get("id")
                    errors = zone_response_json.get("errors", [])
                    zone_response.raise_for_status()

                # 4. Add or get a zone subscription

                # See if one already exists
                subscription_response = requests.get(
                    f"{base_url}/zones/{zone_id}/subscription", headers=headers, timeout=5
                )
                subscription_response_json = subscription_response.json()
                logger.debug(f"get subscription: {subscription_response_json}")

                # Create a subscription if one doesn't exist already.
                # If it doesn't, we get this error message (code 1207):
                # Add a core subscription first and try again. The zone does not have an active core subscription.
                # Note that status code and error code are different here.
                if subscription_response.status_code == 404:
                    subscription_response = requests.post(
                        f"{base_url}/zones/{zone_id}/subscription",
                        headers=headers,
                        json={"rate_plan": {"id": "PARTNERS_ENT"}, "frequency": "annual"},
                        timeout=5,
                    )
                    subscription_response.raise_for_status()
                    subscription_response_json = subscription_response.json()
                    logger.info(f"Created subscription: {subscription_response_json}")
                else:
                    subscription_response.raise_for_status()

                # # 5. Create DNS record
                # # Format the DNS record according to Cloudflare's API requirements
                dns_response = requests.post(
                    f"{base_url}/zones/{zone_id}/dns_records",
                    headers=headers,
                    json={
                        "type": "A",
                        "name": form.cleaned_data["name"],
                        "content": form.cleaned_data["content"],
                        "ttl": int(form.cleaned_data["ttl"]),
                        "comment": "Test record (will need clean up)",
                    },
                    timeout=5,
                )
                dns_response_json = dns_response.json()
                logger.info(f"Created DNS record: {dns_response_json}")
                errors = dns_response_json.get("errors", [])
                dns_response.raise_for_status()
                dns_name = dns_response_json["result"]["name"]
                messages.success(request, f"DNS A record '{dns_name}' created successfully.")
            except Exception as err:
                logger.error(f"Error creating DNS A record for {self.object.name}: {err}")
                messages.error(request, f"An error occurred: {err}")
            finally:
                if errors:
                    messages.error(request, f"Request errors: {errors}")
        return super().post(request)


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

        # Ensure at least 3 fields, filled or empty
        while len(initial_data) < 2:
            initial_data.append({})

        return initial_data

    def get_success_url(self):
        """Redirect to the nameservers page for the domain."""
        return reverse("domain-dns-nameservers", kwargs={"pk": self.object.pk})

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
            if i < 2:
                form.fields["server"].required = True
            else:
                form.fields["server"].required = False
                form.fields["server"].label += " (optional)"
            form.fields["domain"].initial = self.object.name
        return formset

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using DomainBaseView and FormMixin
        """
        self._get_domain(request)
        formset = self.get_form()

        logger.debug("got formet")

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
        return reverse("domain-dns-dnssec", kwargs={"pk": self.object.pk})

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

        # Ensure at least 1 record, filled or empty
        while len(initial_data) == 0:
            initial_data.append({})

        return initial_data

    def get_success_url(self):
        """Redirect to the DS data page for the domain."""
        return reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.object.pk})

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
        override = False

        # This is called by the form cancel button,
        # and also by the modal's X and cancel buttons
        if "btn-cancel-click" in request.POST:
            url = self.get_success_url()
            return HttpResponseRedirect(url)

        # This is called by the Disable DNSSEC modal to override
        if "disable-override-click" in request.POST:
            override = True

        # This is called when all DNSSEC data has been deleted and the
        # Save button is pressed
        if len(formset) == 0 and formset.initial != [{}] and override is False:
            # trigger the modal
            # get context data from super() rather than self
            # to preserve the context["form"]
            context = super().get_context_data(form=formset)
            context["trigger_modal"] = True
            return self.render_to_response(context)

        if formset.is_valid() or override:
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset, **kwargs):
        """The formset is valid, perform something with it."""

        # Set the dnssecdata from the formset
        dnssecdata = extensions.DNSSECExtension()

        for form in formset:
            try:
                # if 'delete' not in form.cleaned_data
                # or form.cleaned_data['delete'] == False:
                dsrecord = {
                    "keyTag": form.cleaned_data["key_tag"],
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


class DomainSecurityEmailView(DomainFormBaseView):
    """Domain security email editing view."""

    template_name = "domain_security_email.html"
    form_class = DomainSecurityEmailForm

    def get_initial(self):
        """The initial value for the form."""
        initial = super().get_initial()
        security_contact = self.object.security_contact

        invalid_emails = [DefaultEmail.PUBLIC_CONTACT_DEFAULT.value, DefaultEmail.LEGACY_DEFAULT.value]
        if security_contact is None or security_contact.email in invalid_emails:
            initial["security_email"] = None
            return initial
        initial["security_email"] = security_contact.email
        return initial

    def get_success_url(self):
        """Redirect to the security email page for the domain."""
        return reverse("domain-security-email", kwargs={"pk": self.object.pk})

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


class DomainUsersView(DomainBaseView):
    """Domain managers page in the domain details."""

    template_name = "domain_users.html"

    def get_context_data(self, **kwargs):
        """The initial value for the form (which is a formset here)."""
        context = super().get_context_data(**kwargs)

        # Add conditionals to the context (such as "can_delete_users")
        context = self._add_booleans_to_context(context)

        # Get portfolio from session (if set)
        portfolio = self.request.session.get("portfolio")

        # Add domain manager roles separately in order to also pass admin status
        context = self._add_domain_manager_roles_to_context(context, portfolio)

        # Add domain invitations separately in order to also pass admin status
        context = self._add_invitations_to_context(context, portfolio)

        # Get the email of the current user
        context["current_user_email"] = self.request.user.email

        return context

    def get(self, request, *args, **kwargs):
        """Get method for DomainUsersView."""
        # Call the parent class's `get` method to get the response and context
        response = super().get(request, *args, **kwargs)

        # Ensure context is available after the parent call
        context = response.context_data if hasattr(response, "context_data") else {}

        # Check if context contains `domain_managers_roles` and its length is 1
        if context.get("domain_manager_roles") and len(context["domain_manager_roles"]) == 1:
            # Add an info message
            messages.info(request, "This domain has one manager. Adding more can prevent issues.")

        return response

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

    def _add_booleans_to_context(self, context):
        # Determine if the current user can delete managers
        domain_pk = None
        can_delete_users = False

        if self.kwargs is not None and "pk" in self.kwargs:
            domain_pk = self.kwargs["pk"]
            # Prevent the end user from deleting themselves as a manager if they are the
            # only manager that exists on a domain.
            can_delete_users = UserDomainRole.objects.filter(domain__id=domain_pk).count() > 1

        context["can_delete_users"] = can_delete_users
        return context


class DomainAddUserView(DomainFormBaseView):
    """Inside of a domain's user management, a form for adding users.

    Multiple inheritance is used here for permissions, form handling, and
    details of the individual domain.
    """

    template_name = "domain_add_user.html"
    form_class = DomainAddUserForm

    def get_success_url(self):
        return reverse("domain-users", kwargs={"pk": self.object.pk})

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
            if (
                flag_is_active_for_user(requestor, "organization_feature")
                and not flag_is_active_for_user(requestor, "multiple_portfolios")
                and domain_org is not None
                and requestor_can_update_portfolio
                and not member_of_this_org
            ):
                send_portfolio_invitation_email(email=requested_email, requestor=requestor, portfolio=domain_org)
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
        send_domain_invitation_email(
            email=email,
            requestor=requestor,
            domains=self.object,
            is_member_of_different_org=member_of_different_org,
        )
        DomainInvitation.objects.get_or_create(email=email, domain=self.object)
        messages.success(self.request, f"{email} has been invited to the domain: {self.object}")

    def _handle_existing_user(self, email, requestor, requested_user, member_of_different_org):
        """Handle adding an existing user to the domain."""
        send_domain_invitation_email(
            email=email,
            requestor=requestor,
            domains=self.object,
            is_member_of_different_org=member_of_different_org,
            requested_user=requested_user,
        )
        UserDomainRole.objects.create(
            user=requested_user,
            domain=self.object,
            role=UserDomainRole.Roles.MANAGER,
        )
        messages.success(self.request, f"Added user {email}.")


class DomainInvitationCancelView(SuccessMessageMixin, DomainInvitationPermissionCancelView):
    object: DomainInvitation
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
        return reverse("domain-users", kwargs={"pk": self.object.domain.id})

    def get_success_message(self, cleaned_data):
        return f"Canceled invitation to {self.object.email}."


class DomainDeleteUserView(UserDomainRolePermissionDeleteView):
    """Inside of a domain's user management, a form for deleting users."""

    object: UserDomainRole  # workaround for type mismatch in DeleteView

    def get_object(self, queryset=None):
        """Custom get_object definition to grab a UserDomainRole object from a domain_id and user_id"""
        domain_id = self.kwargs.get("pk")
        user_id = self.kwargs.get("user_pk")
        return UserDomainRole.objects.get(domain=domain_id, user=user_id)

    def get_success_url(self):
        """Refreshes the page after a delete is successful"""
        return reverse("domain-users", kwargs={"pk": self.object.domain.id})

    def get_success_message(self, delete_self=False):
        """Returns confirmation content for the deletion event"""

        # Grab the text representation of the user we want to delete
        email_or_name = self.object.user.email
        if email_or_name is None or email_or_name.strip() == "":
            email_or_name = self.object.user

        # If the user is deleting themselves, return a specific message.
        # If not, return something more generic.
        if delete_self:
            message = f"You are no longer managing the domain {self.object.domain}."
        else:
            message = f"Removed {email_or_name} as a manager for this domain."

        return message

    def form_valid(self, form):
        """Delete the specified user on this domain."""

        # Delete the object
        super().form_valid(form)

        # Is the user deleting themselves? If so, display a different message
        delete_self = self.request.user == self.object.user

        # Email domain managers

        # Add a success message
        messages.success(self.request, self.get_success_message(delete_self))
        return redirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        """Custom post implementation to redirect to home in the event that the user deletes themselves"""
        response = super().post(request, *args, **kwargs)

        # If the user is deleting themselves, redirect to home
        delete_self = self.request.user == self.object.user
        if delete_self:
            return redirect(reverse("home"))

        return response
