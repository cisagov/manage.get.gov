"""Views for a single Domain.

Authorization is handled by the `DomainPermissionView`. To ensure that only
authorized users can see information on a domain, every view here should
inherit from `DomainPermissionView` (or DomainInvitationPermissionDeleteView).
"""

import logging

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError
from django.shortcuts import redirect
from django.template import RequestContext
from django.urls import reverse
from django.views.generic.edit import FormMixin

from registrar.models import (
    Domain,
    DomainInformation,
    DomainInvitation,
    User,
    UserDomainRole,
)
from registrar.models.public_contact import PublicContact
from registrar.models.utility.contact_error import ContactError

from ..forms import (
    ContactForm,
    DomainOrgNameAddressForm,
    DomainAddUserForm,
    DomainSecurityEmailForm,
    NameserverFormset,
    DomainDnssecForm,
    DomainDsdataFormset,
    DomainDsdataForm,
    DomainKeydataFormset,
    DomainKeydataForm,
)

from epplibwrapper import (
    common,
    extensions,
    RegistryError,
    CANNOT_CONTACT_REGISTRY,
    GENERIC_ERROR,
)

from ..utility.email import send_templated_email, EmailSendingError
from .utility import DomainPermissionView, DomainInvitationPermissionDeleteView


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


class DomainView(DomainBaseView):

    """Domain detail overview page."""

    template_name = "domain_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        default_email = self.object.get_default_security_contact().email
        context["default_security_email"] = default_email

        security_email = self.object.get_security_email()
        if security_email is None or security_email == default_email:
            context["security_email"] = None
            return context
        context["security_email"] = security_email
        return context


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

        messages.success(
            self.request, "The organization name and mailing address has been updated."
        )

        # superclass has the redirect
        return super().form_valid(form)


class DomainAuthorizingOfficialView(DomainFormBaseView):
    """Domain authorizing official editing view."""

    model = Domain
    template_name = "domain_authorizing_official.html"
    context_object_name = "domain"
    form_class = ContactForm

    def get_form_kwargs(self, *args, **kwargs):
        """Add domain_info.authorizing_official instance to make a bound form."""
        form_kwargs = super().get_form_kwargs(*args, **kwargs)
        form_kwargs["instance"] = self.object.domain_info.authorizing_official
        return form_kwargs

    def get_success_url(self):
        """Redirect to the overview page for the domain."""
        return reverse("domain-authorizing-official", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, save the authorizing official."""
        form.save()

        messages.success(
            self.request, "The authorizing official for this domain has been updated."
        )

        # superclass has the redirect
        return super().form_valid(form)


class DomainDNSView(DomainBaseView):
    """DNS Information View."""

    template_name = "domain_dns.html"


class DomainNameserversView(DomainFormBaseView):
    """Domain nameserver editing view."""

    template_name = "domain_nameservers.html"
    form_class = NameserverFormset

    def get_initial(self):
        """The initial value for the form (which is a formset here)."""
        nameservers = self.object.nameservers
        initial_data = []

        if nameservers is not None:
            # Add existing nameservers as initial data
            initial_data.extend({"server": name} for name, *ip in nameservers)

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
        return formset

    def form_valid(self, formset):
        """The formset is valid, perform something with it."""

        # Set the nameservers from the formset
        nameservers = []
        for form in formset:
            try:
                as_tuple = (form.cleaned_data["server"],)
                nameservers.append(as_tuple)
            except KeyError:
                # no server information in this field, skip it
                pass
        self.object.nameservers = nameservers

        messages.success(
            self.request, "The name servers for this domain have been updated."
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
            'class="usa-button" '
            'name="disable_dnssec">Disable DNSSEC</button>'
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
                request.session["dnssec_ds_confirmed"] = False
                request.session["dnssec_key_confirmed"] = False
            elif "enable_dnssec" in request.POST:
                request.session["dnssec_enabled"] = True
                request.session["dnssec_ds_confirmed"] = False
                request.session["dnssec_key_confirmed"] = False

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

        if dnssecdata is not None:
            if dnssecdata.keyData is not None:
                # TODO: Throw an error
                # Note: This is moot if we're
                # removing key data
                pass

            if dnssecdata.dsData is not None:
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
        """Redirect to the DS Data page for the domain."""
        return reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        """Adjust context from FormMixin for formsets."""
        context = super().get_context_data(**kwargs)
        # use "formset" instead of "form" for the key
        context["formset"] = context.pop("form")

        # set the dnssec_ds_confirmed flag in the context for this view
        # based either on the existence of DS Data in the domain,
        # or on the flag stored in the session
        dnssecdata: extensions.DNSSECExtension = self.object.dnssecdata

        if dnssecdata is not None and dnssecdata.dsData is not None:
            self.request.session["dnssec_ds_confirmed"] = True

        context["dnssec_ds_confirmed"] = self.request.session.get(
            "dnssec_ds_confirmed", False
        )
        return context

    def post(self, request, *args, **kwargs):
        """Formset submission posts to this view."""
        self._get_domain(request)
        formset = self.get_form()

        if "confirm-ds" in request.POST:
            request.session["dnssec_ds_confirmed"] = True
            request.session["dnssec_key_confirmed"] = False
            return super().form_valid(formset)

        if "btn-cancel-click" in request.POST:
            return redirect("/", {"formset": formset}, RequestContext(request))

        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
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
            errmsg = "Error updating DNSSEC data in the registry."
            logger.error(errmsg)
            logger.error(err)
            messages.error(self.request, errmsg)
            return self.form_invalid(formset)
        else:
            messages.success(
                self.request, "The DS Data records for this domain have been updated."
            )
            # superclass has the redirect
            return super().form_valid(formset)


class DomainKeyDataView(DomainFormBaseView):
    """Domain DNSSEC key data editing view."""

    template_name = "domain_keydata.html"
    form_class = DomainKeydataFormset
    form = DomainKeydataForm

    def get_initial(self):
        """The initial value for the form (which is a formset here)."""
        dnssecdata: extensions.DNSSECExtension = self.object.dnssecdata
        initial_data = []

        if dnssecdata is not None:
            if dnssecdata.dsData is not None:
                # TODO: Throw an error?
                # Note: this is moot if we're
                # removing Key data
                pass

            if dnssecdata.keyData is not None:
                # Add existing keydata as initial data
                initial_data.extend(
                    {
                        "flag": record.flags,
                        "protocol": record.protocol,
                        "algorithm": record.alg,
                        "pub_key": record.pubKey,
                    }
                    for record in dnssecdata.keyData
                )

        # Ensure at least 1 record, filled or empty
        while len(initial_data) == 0:
            initial_data.append({})

        return initial_data

    def get_success_url(self):
        """Redirect to the Key Data page for the domain."""
        return reverse("domain-dns-dnssec-keydata", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        """Adjust context from FormMixin for formsets."""
        context = super().get_context_data(**kwargs)
        # use "formset" instead of "form" for the key
        context["formset"] = context.pop("form")

        # set the dnssec_key_confirmed flag in the context for this view
        # based either on the existence of Key Data in the domain,
        # or on the flag stored in the session
        dnssecdata: extensions.DNSSECExtension = self.object.dnssecdata

        if dnssecdata is not None and dnssecdata.keyData is not None:
            self.request.session["dnssec_key_confirmed"] = True

        context["dnssec_key_confirmed"] = self.request.session.get(
            "dnssec_key_confirmed", False
        )
        return context

    def post(self, request, *args, **kwargs):
        """Formset submission posts to this view."""
        self._get_domain(request)
        formset = self.get_form()

        if "confirm-key" in request.POST:
            request.session["dnssec_key_confirmed"] = True
            request.session["dnssec_ds_confirmed"] = False
            self.object.save()
            return super().form_valid(formset)

        if "btn-cancel-click" in request.POST:
            return redirect("/", {"formset": formset}, RequestContext(request))

        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        """The formset is valid, perform something with it."""

        # Set the nameservers from the formset
        dnssecdata = extensions.DNSSECExtension()

        for form in formset:
            try:
                # if 'delete' not in form.cleaned_data
                # or form.cleaned_data['delete'] == False:
                keyrecord = {
                    "flags": int(form.cleaned_data["flag"]),
                    "protocol": int(form.cleaned_data["protocol"]),
                    "alg": int(form.cleaned_data["algorithm"]),
                    "pubKey": form.cleaned_data["pub_key"],
                }
                if dnssecdata.keyData is None:
                    dnssecdata.keyData = []
                dnssecdata.keyData.append(common.DNSSECKeyData(**keyrecord))
            except KeyError:
                # no server information in this field, skip it
                pass
        try:
            self.object.dnssecdata = dnssecdata
        except RegistryError as err:
            errmsg = "Error updating DNSSEC data in the registry."
            logger.error(errmsg)
            logger.error(err)
            messages.error(self.request, errmsg)
            return self.form_invalid(formset)
        else:
            messages.success(
                self.request, "The Key Data records for this domain have been updated."
            )
            # superclass has the redirect
            return super().form_valid(formset)


class DomainYourContactInformationView(DomainFormBaseView):
    """Domain your contact information editing view."""

    template_name = "domain_your_contact_information.html"
    form_class = ContactForm

    def get_form_kwargs(self, *args, **kwargs):
        """Add domain_info.submitter instance to make a bound form."""
        form_kwargs = super().get_form_kwargs(*args, **kwargs)
        form_kwargs["instance"] = self.request.user.contact
        return form_kwargs

    def get_success_url(self):
        """Redirect to the your contact information for the domain."""
        return reverse("domain-your-contact-information", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """The form is valid, call setter in model."""

        # Post to DB using values from the form
        form.save()

        messages.success(
            self.request, "Your contact information for this domain has been updated."
        )

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
        if security_contact is None or security_contact.email == "dotgov@cisa.dhs.gov":
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
            messages.error(self.request, CANNOT_CONTACT_REGISTRY)
            return redirect(self.get_success_url())

        contact.email = new_email

        try:
            contact.save()
        except RegistryError as Err:
            if Err.is_connection_error():
                messages.error(self.request, CANNOT_CONTACT_REGISTRY)
                logger.error(f"Registry connection error: {Err}")
            else:
                messages.error(self.request, GENERIC_ERROR)
                logger.error(f"Registry error: {Err}")
        except ContactError as Err:
            messages.error(self.request, GENERIC_ERROR)
            logger.error(f"Generic registry error: {Err}")
        else:
            messages.success(
                self.request, "The security email for this domain has been updated."
            )

        # superclass has the redirect
        return redirect(self.get_success_url())


class DomainUsersView(DomainBaseView):
    """Domain managers page in the domain details."""

    template_name = "domain_users.html"


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
        return self.request.build_absolute_uri(
            reverse("domain", kwargs={"pk": self.object.id})
        )

    def _make_invitation(self, email_address):
        """Make a Domain invitation for this email and redirect with a message."""
        invitation, created = DomainInvitation.objects.get_or_create(
            email=email_address, domain=self.object
        )
        if not created:
            # that invitation already existed
            messages.warning(
                self.request,
                f"{email_address} has already been invited to this domain.",
            )
        else:
            # created a new invitation in the database, so send an email
            domaininfo = DomainInformation.objects.filter(domain=self.object)
            first = domaininfo.first().creator.first_name
            last = domaininfo.first().creator.last_name
            full_name = f"{first} {last}"

            try:
                send_templated_email(
                    "emails/domain_invitation.txt",
                    "emails/domain_invitation_subject.txt",
                    to_address=email_address,
                    context={
                        "domain_url": self._domain_abs_url(),
                        "domain": self.object,
                        "full_name": full_name,
                    },
                )
            except EmailSendingError:
                messages.warning(self.request, "Could not send email invitation.")
                logger.warn(
                    "Could not sent email invitation to %s for domain %s",
                    email_address,
                    self.object,
                    exc_info=True,
                )
            else:
                messages.success(
                    self.request, f"Invited {email_address} to this domain."
                )

        return redirect(self.get_success_url())

    def form_valid(self, form):
        """Add the specified user on this domain."""
        requested_email = form.cleaned_data["email"]
        # look up a user with that email
        try:
            requested_user = User.objects.get(email=requested_email)
        except User.DoesNotExist:
            # no matching user, go make an invitation
            return self._make_invitation(requested_email)

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


class DomainInvitationDeleteView(
    DomainInvitationPermissionDeleteView, SuccessMessageMixin
):
    object: DomainInvitation  # workaround for type mismatch in DeleteView

    def get_success_url(self):
        return reverse("domain-users", kwargs={"pk": self.object.domain.id})

    def get_success_message(self, cleaned_data):
        return f"Successfully canceled invitation for {self.object.email}."
