"""Permissions-related mixin classes."""

from django.contrib.auth.mixins import PermissionRequiredMixin

from registrar.models import (
    DomainApplication,
    DomainInvitation,
    DomainInformation,
    UserDomainRole,
)
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
        """

        if not self.request.user.is_authenticated:
            return False

        pk = self.kwargs["pk"]
        # If pk is none then something went very wrong...
        if pk is None:
            raise ValueError("Primary key is None")

        # user needs to have a role on the domain
        if UserDomainRole.objects.filter(
            user=self.request.user, domain__id=pk
        ).exists():
            return True

        # ticket 806
        requested_domain: DomainInformation = None
        try:
            requested_domain = DomainInformation.objects.get(id=pk)
        except DomainInformation.DoesNotExist:
            # Q: While testing, I saw that, application-wide, if you go to a domain
            # that does not exist, for example,
            # https://getgov-staging.app.cloud.gov/domain/73333,
            # the page throws a 403 error, instead of a 404.
            # Do we want it to throw a 404 instead?
            # Basically, should this be Http404()?
            logger.debug(f"Domain with PK {pk} does not exist")
            return False

        # Analysts may manage domains, when they are in these statuses:
        valid_domain_statuses = [
            DomainApplication.APPROVED,
            DomainApplication.IN_REVIEW,
            DomainApplication.REJECTED,
            DomainApplication.ACTION_NEEDED,
        ]

        # Check if the user is permissioned...
        user_is_analyst_or_superuser = (
            self.request.user.is_staff or self.request.user.is_superuser
        )

        session = self.request.session
        # Check if the user is attempting a valid edit action.
        can_do_action = (
            "analyst_action" in session
            and "analyst_action_location" in session
            and session["analyst_action_location"] == pk
        )
        
        # If the valid session keys exist, if the user is permissioned,
        # and if its in a valid status
        if (
            can_do_action
            and user_is_analyst_or_superuser
            and requested_domain.domain_application.status in valid_domain_statuses
        ):
            return True

        # ticket 796
        # if domain.application__status != 'approved'
        #     return false

        # if we need to check more about the nature of role, do it here.
        return False


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
