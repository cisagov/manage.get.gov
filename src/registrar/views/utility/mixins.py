"""Permissions-related mixin classes."""

from django.contrib.auth.mixins import PermissionRequiredMixin

from registrar.models import UserDomainRole, DomainApplication, DomainInvitation


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
        """

        # ticket 806
        # if self.request.user is staff or admin and
        # domain.application__status = 'approved' or 'rejected' or 'action needed'
        #     return True

        if not self.request.user.is_authenticated:
            return False

        # user needs to have a role on the domain
        if not UserDomainRole.objects.filter(
            user=self.request.user, domain__id=self.kwargs["pk"]
        ).exists():
            return False

        # The user has an ineligible flag
        if self.request.user.is_restricted():
            return False

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


class ApplicationWizardPermission(PermissionsLoginMixin):

    """Does the logged-in user have permission to start or edit an application?"""

    def has_permission(self):
        """Check if this user has permission to start or edit an application.

        The user is in self.request.user
        """

        # The user has an ineligible flag
        if self.request.user.is_restricted():
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
