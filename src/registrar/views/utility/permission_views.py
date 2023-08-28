"""View classes that enforce authorization."""

import abc  # abstract base class

from django.views.generic import DetailView, DeleteView

from registrar.models import Domain, DomainApplication, DomainInvitation


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

    def log_analyst_form_actions(
        self, form_class_name, printable_object_info, changes=None
    ):
        """Generates a log for when key 'analyst_action' exists on the session.
        Follows this format:

        for field, new_value in changes.items():
                "{user_type} '{self.request.user}'
                set field '{field}': '{new_value}'
                under class '{form_class_name}'
                in domain '{printable_object_info}'"
        """
        if "analyst_action" in self.request.session:
            action = self.request.session["analyst_action"]

            user_type = "Analyst"
            if self.request.user.is_superuser:
                user_type = "Superuser"

            # Template for potential future expansion,
            # in the event we want more logging granularity.
            # Could include things such as 'view'
            # or 'copy', for instance.
            match action:
                case "edit":
                    # Q: do we want to be logging on every changed field?
                    # I could see that becoming spammy log-wise,
                    # but it may also be important.
                    if changes is not None:
                        # Logs every change made to the domain field
                        # noqa for readability/format
                        for field, new_value in changes.items():
                            logger.info(
                                f"""
                                An analyst or superuser made alterations to a domain: 
                                {user_type} '{self.request.user}' 
                                set field '{field}': '{new_value}' 
                                under class '{form_class_name}' 
                                in domain '{printable_object_info}'
                                """  # noqa
                            )
                    else:
                        # noqa here as breaking this up further leaves it hard to read
                        logger.info(
                            f"{user_type} {self.request.user} edited {form_class_name} in {printable_object_info}"  # noqa
                        )

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
