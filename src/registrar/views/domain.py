"""Views for a single Domain.

Authorization is handled by the `DomainPermissionView`. To ensure that only
authorized users can see information on a domain, every view here should
inherit from `DomainPermissionView` (or DomainInvitationPermissionDeleteView).
"""

import logging

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic.edit import FormMixin
from django.conf import settings
from registrar.forms.domain import DomainSuborganizationForm
from registrar.models import (
    Domain,
    DomainRequest,
    DomainInformation,
    DomainInvitation,
    User,
    UserDomainRole,
    PublicContact,
)
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

from ..forms import (
    UserForm,
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
from .utility import DomainPermissionView, DomainInvitationPermissionDeleteView
from waffle.decorators import waffle_flag

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
        if self.request.user.has_domains_portfolio_permission(portfolio):
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


class DomainOrgNameAddressView(DomainFormBaseView):
    """Organization name and mailing address view"""

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

        if "btn-cancel-click" in request.POST:
            url = self.get_success_url()
            return HttpResponseRedirect(url)

        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        """The formset is valid, perform something with it."""

        self.request.session["nameservers_form_domain"] = self.object

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

        # Create HTML for the modal button
        modal_button = (
            '<button type="submit" '
            'class="usa-button usa-button--secondary" '
            'name="disable_dnssec">Confirm</button>'
        )

        context["modal_button"] = modal_button
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
            # Create HTML for the modal button
            modal_button = (
                '<button type="submit" '
                'class="usa-button usa-button--secondary" '
                'name="disable-override-click">Remove all DS data</button>'
            )

            # context to back out of a broken form on all fields delete
            context["modal_button"] = modal_button
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
            messages.success(self.request, "The DS data records for this domain have been updated.")
            # superclass has the redirect
            return super().form_valid(formset)


class DomainYourContactInformationView(DomainFormBaseView):
    """Domain your contact information editing view."""

    template_name = "domain_your_contact_information.html"
    form_class = UserForm

    @waffle_flag("!profile_feature")  # type: ignore
    def dispatch(self, request, *args, **kwargs):  # type: ignore
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, *args, **kwargs):
        """Add domain_info.submitter instance to make a bound form."""
        form_kwargs = super().get_form_kwargs(*args, **kwargs)
        form_kwargs["instance"] = self.request.user
        return form_kwargs

    def get_success_url(self):
        """Redirect to the your contact information for the domain."""
        return reverse("domain-your-contact-information", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, call setter in model."""

        # Post to DB using values from the form
        form.save()

        messages.success(self.request, "Your contact information for all your domains has been updated.")

        # superclass has the redirect
        return super().form_valid(form)


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
            messages.success(self.request, "The security email for this domain has been updated.")

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

        # Add modal buttons to the context (such as for delete)
        context = self._add_modal_buttons_to_context(context)

        # Get the email of the current user
        context["current_user_email"] = self.request.user.email

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

    def _add_modal_buttons_to_context(self, context):
        """Adds modal buttons (and their HTML) to the context"""
        # Create HTML for the modal button
        modal_button = (
            '<button type="submit" '
            'class="usa-button usa-button--secondary" '
            'name="delete_domain_manager">Yes, remove domain manager</button>'
        )
        context["modal_button"] = modal_button

        # Create HTML for the modal button when deleting yourself
        modal_button_self = (
            '<button type="submit" '
            'class="usa-button usa-button--secondary" '
            'name="delete_domain_manager_self">Yes, remove myself</button>'
        )
        context["modal_button_self"] = modal_button_self

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

    def _domain_abs_url(self):
        """Get an absolute URL for this domain."""
        return self.request.build_absolute_uri(reverse("domain", kwargs={"pk": self.object.id}))

    def _send_domain_invitation_email(self, email: str, requestor: User, add_success=True):
        """Performs the sending of the domain invitation email,
        does not make a domain information object
        email: string- email to send to
        add_success: bool- default True indicates:
        adding a success message to the view if the email sending succeeds

        raises EmailSendingError
        """

        # Set a default email address to send to for staff
        requestor_email = settings.DEFAULT_FROM_EMAIL

        # Check if the email requestor has a valid email address
        if not requestor.is_staff and requestor.email is not None and requestor.email.strip() != "":
            requestor_email = requestor.email
        elif not requestor.is_staff:
            messages.error(self.request, "Can't send invitation email. No email is associated with your account.")
            logger.error(
                f"Can't send email to '{email}' on domain '{self.object}'."
                f"No email exists for the requestor '{requestor.username}'.",
                exc_info=True,
            )
            return None

        try:
            send_templated_email(
                "emails/domain_invitation.txt",
                "emails/domain_invitation_subject.txt",
                to_address=email,
                context={
                    "domain_url": self._domain_abs_url(),
                    "domain": self.object,
                    "requestor_email": requestor_email,
                },
            )
        except EmailSendingError as exc:
            logger.warn(
                "Could not sent email invitation to %s for domain %s",
                email,
                self.object,
                exc_info=True,
            )
            raise EmailSendingError("Could not send email invitation.") from exc
        else:
            if add_success:
                messages.success(self.request, f"{email} has been invited to this domain.")

    def _make_invitation(self, email_address: str, requestor: User):
        """Make a Domain invitation for this email and redirect with a message."""
        # Check to see if an invite has already been sent (NOTE: we do not want to create an invite just yet.)
        try:
            invite = DomainInvitation.objects.get(email=email_address, domain=self.object)
            # that invitation already existed
            if invite is not None:
                messages.warning(
                    self.request,
                    f"{email_address} has already been invited to this domain.",
                )
        except DomainInvitation.DoesNotExist:
            # Try to send the invitation.  If it succeeds, add it to the DomainInvitation table.
            try:
                self._send_domain_invitation_email(email=email_address, requestor=requestor)
            except EmailSendingError:
                messages.warning(self.request, "Could not send email invitation.")
            else:
                # (NOTE: only create a domainInvitation if the e-mail sends correctly)
                DomainInvitation.objects.get_or_create(email=email_address, domain=self.object)
        return redirect(self.get_success_url())

    def form_valid(self, form):
        """Add the specified user on this domain.
        Throws EmailSendingError."""
        requested_email = form.cleaned_data["email"]
        requestor = self.request.user
        # look up a user with that email
        try:
            requested_user = User.objects.get(email=requested_email)
        except User.DoesNotExist:
            # no matching user, go make an invitation
            return self._make_invitation(requested_email, requestor)
        else:
            # if user already exists then just send an email
            try:
                self._send_domain_invitation_email(requested_email, requestor, add_success=False)
            except EmailSendingError:
                logger.warn(
                    "Could not send email invitation (EmailSendingError)",
                    self.object,
                    exc_info=True,
                )
                messages.warning(self.request, "Could not send email invitation.")
            except Exception:
                logger.warn(
                    "Could not send email invitation (Other Exception)",
                    self.object,
                    exc_info=True,
                )
                messages.warning(self.request, "Could not send email invitation.")

        try:
            UserDomainRole.objects.create(
                user=requested_user,
                domain=self.object,
                role=UserDomainRole.Roles.MANAGER,
            )
        except IntegrityError:
            # User already has the desired role! Do nothing??
            pass

        messages.success(self.request, f"Added user {requested_email}.")

        return redirect(self.get_success_url())


# The order of the superclasses matters here. BaseDeleteView has a bug where the
# "form_valid" function does not call super, so it cannot use SuccessMessageMixin.
# The workaround is to use SuccessMessageMixin first.
class DomainInvitationDeleteView(SuccessMessageMixin, DomainInvitationPermissionDeleteView):
    object: DomainInvitation  # workaround for type mismatch in DeleteView

    def post(self, request, *args, **kwargs):
        """Override post method in order to error in the case when the
        domain invitation status is RETRIEVED"""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid() and self.object.status == self.object.DomainInvitationStatus.INVITED:
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
