"""View for a single Domain."""

from django import forms
from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic.edit import FormMixin

from registrar.models import Domain, User, UserDomainRole

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


class DomainAddUserForm(DomainPermission, forms.Form):

    """Form for adding a user to a domain."""

    email = forms.EmailField(label="Email")

    def clean_email(self):
        requested_email = self.cleaned_data["email"]
        try:
            User.objects.get(email=requested_email)
        except User.DoesNotExist:
            # TODO: send an invitation email to a non-existent user
            raise forms.ValidationError("That user does not exist in this system.")
        return requested_email


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
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Add the specified user on this domain."""
        requested_email = form.cleaned_data["email"]
        # look up a user with that email
        # they should exist because we checked in clean_email
        requested_user = User.objects.get(email=requested_email)

        try:
            UserDomainRole.objects.create(
                user=requested_user, domain=self.object, role=UserDomainRole.Roles.ADMIN
            )
        except IntegrityError:
            # User already has the desired role! Do nothing??
            pass

        messages.success(self.request, f"Added user {requested_email}.")
        return redirect(self.get_success_url())
