"""View classes that enforce authorization."""

import abc  # abstract base class

from django.views.generic import DetailView, DeleteView, TemplateView
from django.contrib.contenttypes.models import ContentType
from registrar.models import Domain, DomainApplication, DomainInvitation
from django.contrib.admin.models import LogEntry, CHANGE

from .mixins import (
    DomainPermission,
    DomainApplicationPermission,
    DomainInvitationPermission,
    ApplicationWizardPermission,
)
import logging

logger = logging.getLogger(__name__)


class DomainPermissionView(DomainPermission, DetailView, abc.ABC):

    """Abstract base view for domains that enforces permissions.

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # DetailView property for what model this is viewing
    model = Domain
    # variable name in template context for the model object
    context_object_name = "domain"

    # Adds context information for user permissions
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["is_analyst_or_superuser"] = user.is_staff or user.is_superuser
        # Stored in a variable for the linter
        action = "analyst_action"
        action_location = "analyst_action_location"
        # Flag to see if an analyst is attempting to make edits
        if action in self.request.session:
            context[action] = self.request.session[action]
        if action_location in self.request.session:
            context[action_location] = self.request.session[action_location]

        return context

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError


class DomainApplicationPermissionView(DomainApplicationPermission, DetailView, abc.ABC):

    """Abstract base view for domain applications that enforces permissions

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # DetailView property for what model this is viewing
    model = DomainApplication
    # variable name in template context for the model object
    context_object_name = "domainapplication"

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError


class ApplicationWizardPermissionView(
    ApplicationWizardPermission, TemplateView, abc.ABC
):

    """Abstract base view for the application form that enforces permissions

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError


class DomainInvitationPermissionDeleteView(
    DomainInvitationPermission, DeleteView, abc.ABC
):

    """Abstract view for deleting a domain invitation.

    This one is fairly specialized, but this is the only thing that we do
    right now with domain invitations. We still have the full
    `DomainInvitationPermission` class, but here we just pair it with a
    DeleteView.
    """

    model = DomainInvitation
    object: DomainInvitation  # workaround for type mismatch in DeleteView
