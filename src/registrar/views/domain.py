"""View for a single Domain."""

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic.edit import DeleteView, FormMixin

from registrar.models import Domain, DomainInvitation, User, UserDomainRole

from ..forms import DomainAddUserForm
from ..utility.email import send_templated_email, EmailSendingError
from .utility import DomainPermission


class DomainView(DomainPermission, DetailView):

    """Domain detail overview page."""

    model = Domain
    template_name = "domain_detail.html"
    context_object_name = "domain"


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
                    "emails/domain_invitation.subject.txt",
                    to_address=email_address,
                    context={
                        "domain_url": self._domain_abs_url(),
                        "domain": self.object,
                    },
                )
            except EmailSendingError:
                messages.warning(self.request, "Could not send email invitation.")
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
