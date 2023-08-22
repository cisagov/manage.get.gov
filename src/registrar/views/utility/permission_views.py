"""View classes that enforce authorization."""

import abc  # abstract base class

from django.views.generic import DetailView, DeleteView

from registrar.models import Domain, DomainApplication, DomainInvitation
from registrar.models.domain_information import DomainInformation

from .mixins import (
    DomainPermission,
    DomainApplicationPermission,
    DomainInvitationPermission,
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
        # Q: is there a more efficent way to do this?
        # Searches by creator_id instead of creator,
        # should be slightly faster than by creator...
        is_original_creator = DomainInformation.objects.filter(
            creator_id=self.request.user.id, id=self.kwargs["pk"]
        ).exists()
        context['is_original_creator'] = is_original_creator
        context['is_analyst_or_superuser'] = user.is_superuser or user.is_staff

        # Flag to see if an analyst is attempting to make edits
        if 'analyst_action' in self.request.session:
            context['analyst_action'] = self.request.session['analyst_action']
            # Clear the session variable after use
            # del self.request.session['analyst_action']

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
