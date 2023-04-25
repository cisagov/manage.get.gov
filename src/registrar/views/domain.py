"""View for a single Domain."""

import logging

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError
from django.forms import formset_factory
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic.edit import DeleteView, FormMixin

from registrar.models import Domain, DomainInvitation, User, UserDomainRole

from ..forms import DomainAddUserForm, DomainNameserverForm
from ..utility.email import send_templated_email, EmailSendingError
from .utility import DomainPermission


logger = logging.getLogger(__name__)

NameserverFormset = formset_factory(DomainNameserverForm)


class DomainView(DomainPermission, DetailView):

    """Domain detail overview page."""

    model = Domain
    template_name = "domain_detail.html"
    context_object_name = "domain"


class DomainNameserversView(DomainPermission, FormMixin, DetailView):

    """Domain nameserver editing view."""

    model = Domain
    template_name = "domain_nameservers.html"
    context_object_name = "domain"
    form_class = NameserverFormset

    def get_initial(self):
        """The initial value for the form (which is a formset here)."""
        domain = self.get_object()
        return [{"server": server} for server in domain.nameservers()]

    def get_success_url(self):
        """Redirect to the overview page for the domain."""
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
        print([form.fields["server"].required for form in formset])
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        """The formset is valid, perform something with it."""

        # Set the nameservers from the formset
        nameservers = []
        for form in formset:
            print(form.cleaned_data)
            try:
                nameservers.append(form.cleaned_data["server"])
            except KeyError:
                # no server information in this field, skip it
                pass
        print("Valid form, got nameservers:", nameservers)
        domain = self.get_object()
        domain.set_nameservers(nameservers)

        messages.success(
            self.request, "The name servers for this domain have been updated"
        )
        # superclass has the redirect
        return super().form_valid(formset)


class DomainUsersView(DomainPermission, DetailView):

    """User management page in the domain details."""

    model = Domain
    template_name = "domain_users.html"
    context_object_name = "domain"


class DomainAddUserView(DomainPermission, FormMixin, DetailView):

    """Inside of a domain's user management, a form for adding users.

    Multiple inheritance is used here for permissions, form handling, and
    details of the individual domain.
    """

    template_name = "domain_add_user.html"
    model = Domain
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
            try:
                send_templated_email(
                    "emails/domain_invitation.txt",
                    "emails/domain_invitation_subject.txt",
                    to_address=email_address,
                    context={
                        "domain_url": self._domain_abs_url(),
                        "domain": self.object,
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


class DomainInvitationDeleteView(SuccessMessageMixin, DeleteView):
    model = DomainInvitation
    object: DomainInvitation  # workaround for type mismatch in DeleteView

    def get_success_url(self):
        return reverse("domain-users", kwargs={"pk": self.object.domain.id})

    def get_success_message(self, cleaned_data):
        return f"Successfully canceled invitation for {self.object.email}."
