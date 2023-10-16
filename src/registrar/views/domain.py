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
from django.urls import reverse
from django.views.generic.edit import FormMixin

from registrar.models import (
    Domain,
    DomainInformation,
    DomainInvitation,
    User,
    UserDomainRole,
)

from ..forms import (
    ContactForm,
    DomainOrgNameAddressForm,
    DomainAddUserForm,
    DomainSecurityEmailForm,
    NameserverFormset,
)
from ..utility.email import send_templated_email, EmailSendingError
from .utility import DomainPermissionView, DomainInvitationPermissionDeleteView


logger = logging.getLogger(__name__)


class DomainView(DomainPermissionView):

    """Domain detail overview page."""

    template_name = "domain_detail.html"


class DomainOrgNameAddressView(DomainPermissionView, FormMixin):
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

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using DetailView and FormMixin together.
        """
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """The form is valid, save the organization name and mailing address."""
        form.save()

        messages.success(
            self.request, "The organization name and mailing address has been updated."
        )

        # superclass has the redirect
        return super().form_valid(form)


class DomainAuthorizingOfficialView(DomainPermissionView, FormMixin):

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

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using DetailView and FormMixin together.
        """
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """The form is valid, save the authorizing official."""
        form.save()

        messages.success(
            self.request, "The authorizing official for this domain has been updated."
        )

        # superclass has the redirect
        return super().form_valid(form)


class DomainNameserversView(DomainPermissionView, FormMixin):

    """Domain nameserver editing view."""

    template_name = "domain_nameservers.html"
    form_class = NameserverFormset

    def get_initial(self):
        """The initial value for the form (which is a formset here)."""
        logger.info("DomainNameserversView.get_initial()")
        domain = self.object
        logger.info("DomainNameserversView.get_initial:: after get_object")
        nameservers = domain.nameservers
        logger.info("DomainNameserversView.get_initial:: after set nameservers")
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
        return reverse("domain-nameservers", kwargs={"pk": self.object.pk})

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

    def post(self, request, *args, **kwargs):
        """Formset submission posts to this view."""
        self.object = self.get_object()
        formset = self.get_form()

        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

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
        domain = self.object
        domain.nameservers = nameservers

        messages.success(
            self.request, "The name servers for this domain have been updated."
        )

        # superclass has the redirect
        return super().form_valid(formset)


class DomainYourContactInformationView(DomainPermissionView, FormMixin):

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

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view."""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            # there is a valid email address in the form
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """The form is valid, call setter in model."""

        # Post to DB using values from the form
        form.save()

        messages.success(
            self.request, "Your contact information for this domain has been updated."
        )

        # superclass has the redirect
        return super().form_valid(form)


class DomainSecurityEmailView(DomainPermissionView, FormMixin):

    """Domain security email editing view."""

    template_name = "domain_security_email.html"
    form_class = DomainSecurityEmailForm

    def get_initial(self):
        """The initial value for the form."""
        domain = self.object
        initial = super().get_initial()
        security_contact = domain.security_contact
        if security_contact is None or security_contact.email == "dotgov@cisa.dhs.gov":
            initial["security_email"] = None
            return initial
        initial["security_email"] = security_contact.email
        return initial

    def get_success_url(self):
        """Redirect to the security email page for the domain."""
        return reverse("domain-security-email", kwargs={"pk": self.object.pk})

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view."""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            # there is a valid email address in the form
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """The form is valid, call setter in model."""

        # Set the security email from the form
        new_email = form.cleaned_data.get("security_email", "")

        domain = self.object
        contact = domain.security_contact
        contact.email = new_email
        contact.save()

        messages.success(
            self.request, "The security email for this domain has been updated."
        )

        # superclass has the redirect
        return redirect(self.get_success_url())


class DomainUsersView(DomainPermissionView):

    """User management page in the domain details."""

    template_name = "domain_users.html"


class DomainAddUserView(DomainPermissionView, FormMixin):

    """Inside of a domain's user management, a form for adding users.

    Multiple inheritance is used here for permissions, form handling, and
    details of the individual domain.
    """

    template_name = "domain_add_user.html"
    form_class = DomainAddUserForm

    def get_success_url(self):
        return reverse("domain-users", kwargs={"pk": self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            # there is a valid email address in the form
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

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
                user=requested_user, domain=self.object, role=UserDomainRole.Roles.ADMIN
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
