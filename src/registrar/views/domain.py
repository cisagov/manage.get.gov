"""View for a single Domain."""

from django import forms
from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic.edit import FormMixin

from registrar.models import Domain, DomainInvitation, User, UserDomainRole

from .utility import DomainPermission


class DomainView(DomainPermission, DetailView):
    model = Domain
    template_name = "domain_detail.html"
    context_object_name = "domain"


class DomainUsersView(DomainPermission, DetailView):
    model = Domain
    template_name = "domain_users.html"
    context_object_name = "domain"


class DomainAddUserForm(DomainPermission, forms.Form):

    """Form for adding a user to a domain."""

    email = forms.EmailField(label="Email")


class DomainAddUserView(DomainPermission, FormMixin, DetailView):
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

    def _make_invitation(self, email_address):
        """Make a Domain invitation for this email and redirect with a message."""
        invitation, created = DomainInvitation.objects.get_or_create(email=email_address, domain=self.object)
        if not created:
            # that invitation already existed
            messages.warning(self.request, f"{email_address} has already been invited to this domain.")
        else:
            messages.success(self.request, f"Invited {email_address} to this domain.")
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
