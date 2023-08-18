"""Permissions-related mixin classes."""

from django.contrib.auth.mixins import PermissionRequiredMixin

from registrar.models import UserDomainRole, DomainApplication, DomainInvitation
import logging
logger = logging.getLogger(__name__)

class PermissionsLoginMixin(PermissionRequiredMixin):

    """Mixin that redirects to login page if not logged in, otherwise 403."""

    def handle_no_permission(self):
        self.raise_exception = self.request.user.is_authenticated
        return super().handle_no_permission()


class DomainPermission(PermissionsLoginMixin):

    """Does the logged-in user have access to this domain?"""

    def has_permission(self):
        """Check if this user has access to this domain.

        The user is in self.request.user and the domain needs to be looked
        up from the domain's primary key in self.kwargs["pk"]

        analysts and superusers are exempt
        """

        # ticket 806
        # if self.request.user is staff or admin and
        # domain.application__status = 'approved' or 'rejected' or 'action needed'
        #     return True

        if not self.request.user.is_authenticated:
            return False

        # user needs to be the creator of the application
        # this query is empty if there isn't a domain application with this
        # id and this user as creator
        user_is_creator: bool = DomainApplication.objects.filter(
            creator=self.request.user, id=self.kwargs["pk"]
        ).exists()
        user_is_analyst_or_superuser = self.request.user.is_staff or self.request.user.is_superuser
        # user needs to have a role on the domain
        if not user_is_creator and not user_is_analyst_or_superuser:
            return False

        # ticket 796
        # if domain.application__status != 'approved'
        #     return false

        # if we need to check more about the nature of role, do it here.
        return True


class DomainApplicationPermission(PermissionsLoginMixin):

    """Does the logged-in user have access to this domain application?"""

    def has_permission(self):
        """Check if this user has access to this domain application.

        The user is in self.request.user and the domain needs to be looked
        up from the domain's primary key in self.kwargs["pk"]
        """
        if not self.request.user.is_authenticated:
            return False

        # user needs to be the creator of the application
        # this query is empty if there isn't a domain application with this
        # id and this user as creator
        if not DomainApplication.objects.filter(
            creator=self.request.user, id=self.kwargs["pk"]
        ).exists():
            return False

        return True


class DomainInvitationPermission(PermissionsLoginMixin):

    """Does the logged-in user have access to this domain invitation?

    A user has access to a domain invitation if they have a role on the
    associated domain.
    """

    def has_permission(self):
        """Check if this user has a role on the domain of this invitation."""
        if not self.request.user.is_authenticated:
            return False

        if not DomainInvitation.objects.filter(
            id=self.kwargs["pk"], domain__permissions__user=self.request.user
        ).exists():
            return False

        return True
