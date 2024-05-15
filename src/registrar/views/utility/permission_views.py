"""View classes that enforce authorization."""

import abc  # abstract base class

from django.contrib.auth import get_user_model
from django.views.generic import DetailView, DeleteView, TemplateView
from registrar.models import Domain, DomainRequest, DomainInvitation, User
from registrar.models.contact import Contact
from registrar.models.user_domain_role import UserDomainRole

from .mixins import (
    DomainPermission,
    DomainRequestPermission,
    DomainRequestPermissionWithdraw,
    DomainInvitationPermission,
    DomainRequestWizardPermission,
    UserDeleteDomainRolePermission,
    UserProfilePermission,
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
        context["is_analyst_or_superuser"] = user.has_perm("registrar.analyst_access_permission") or user.has_perm(
            "registrar.full_access_permission"
        )
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


class DomainRequestPermissionView(DomainRequestPermission, DetailView, abc.ABC):
    """Abstract base view for domain requests that enforces permissions

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # DetailView property for what model this is viewing
    model = DomainRequest
    # variable name in template context for the model object
    context_object_name = "DomainRequest"

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError


class DomainRequestPermissionWithdrawView(DomainRequestPermissionWithdraw, DetailView, abc.ABC):
    """Abstract base view for domain request withdraw function

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # DetailView property for what model this is viewing
    model = DomainRequest
    # variable name in template context for the model object
    context_object_name = "DomainRequest"

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError


class DomainRequestWizardPermissionView(DomainRequestWizardPermission, TemplateView, abc.ABC):
    """Abstract base view for the domain request form that enforces permissions

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError


class DomainInvitationPermissionDeleteView(DomainInvitationPermission, DeleteView, abc.ABC):
    """Abstract view for deleting a domain invitation.

    This one is fairly specialized, but this is the only thing that we do
    right now with domain invitations. We still have the full
    `DomainInvitationPermission` class, but here we just pair it with a
    DeleteView.
    """

    model = DomainInvitation
    object: DomainInvitation  # workaround for type mismatch in DeleteView


class DomainRequestPermissionDeleteView(DomainRequestPermission, DeleteView, abc.ABC):
    """Abstract view for deleting a DomainRequest."""

    model = DomainRequest
    object: DomainRequest


class UserDomainRolePermissionDeleteView(UserDeleteDomainRolePermission, DeleteView, abc.ABC):
    """Abstract base view for deleting a UserDomainRole.

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # DetailView property for what model this is viewing
    model = UserDomainRole
    # workaround for type mismatch in DeleteView
    object: UserDomainRole

    # variable name in template context for the model object
    context_object_name = "userdomainrole"


class UserProfilePermissionView(UserProfilePermission, DetailView, abc.ABC):
    """Abstract base view for user profile view that enforces permissions.

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # DetailView property for what model this is viewing
    model = Contact
    # variable name in template context for the model object
    context_object_name = "contact"

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError
