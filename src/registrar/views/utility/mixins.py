"""Permissions-related mixin classes."""

from django.contrib.auth.mixins import PermissionRequiredMixin

from registrar.models import (
    DomainApplication,
    DomainInvitation,
    DomainInformation,
    UserDomainRole,
)
import logging
from registrar.models.domain import Domain
from registrar.models.draft_domain import DraftDomain


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

        if self.request.user.is_restricted():
            return False

        pk = self.kwargs["pk"]
        # If pk is none then something went very wrong...
        if pk is None:
            raise ValueError("Primary key is None")

        if self.can_access_other_user_domains(pk):
            return True

        # user needs to have a role on the domain
        if not UserDomainRole.objects.filter(
            user=self.request.user, domain__id=pk
        ).exists():
            return False

        # if we need to check more about the nature of role, do it here.
        return True

    def can_access_other_user_domains(self, pk):
        """Checks to see if an authorized user (staff or superuser)
        can access a domain that they did not create or was invited to.
        """

        # Check if the user is permissioned...
        user_is_analyst_or_superuser = (
            self.request.user.is_staff or self.request.user.is_superuser
        )

        if not user_is_analyst_or_superuser:
            return False

        # Check if the user is attempting a valid edit action.
        # In other words, if the analyst/admin did not click
        # the 'Manage Domain' button in /admin,
        # then they cannot access this page.
        session = self.request.session
        can_do_action = (
            "analyst_action" in session
            and "analyst_action_location" in session
            and session["analyst_action_location"] == pk
        )

        if not can_do_action:
            return False

        # Analysts may manage domains, when they are in these statuses:
        valid_domain_statuses = [
            DomainApplication.APPROVED,
            DomainApplication.IN_REVIEW,
            DomainApplication.REJECTED,
            DomainApplication.ACTION_NEEDED,
            # Edge case - some domains do not have
            # a status or DomainInformation... aka a status of 'None'.
            # It is necessary to access those to correct errors.
            None,
        ]

        wanted_domain = None
        if DomainInformation.objects.filter(id=pk).exists():
            wanted_domain = DomainInformation.objects.get(id=pk)

        # Create a default domain application if it doesn't exist...
        if (
            Domain.objects.filter(id=pk).exists()
            and wanted_domain.domain_application is None
        ):
            self.add_barebones_application_to_domain(
                Domain.objects.get(id=pk), wanted_domain
            )

        if wanted_domain.domain_application.status not in valid_domain_statuses:
            return False

        # Valid session keys exist,
        # the user is permissioned,
        # and it is in a valid status
        return True

    def add_barebones_application_to_domain(self, current_domain, domain_info):
        """Tries to either add a default or existing
        DomainApplication object to a DomainInformation object"""

        # --- Handle DomainInformation --- #
        # Does DomainInformation exist? If not, create one.
        # Otherwise, grab existing
        if Domain.objects.filter(id=pk).exists():
            if not DomainInformation.objects.filter(domain=current_domain).exists():
                domain_info = DomainInformation(
                    creator=self.request.user, domain=current_domain
                )
            else:
                domain_info = DomainInformation.objects.get(domain=current_domain)

        if domain_info.domain_application is not None:
            raise ValueError("DomainApplication already exists")

        # --- Handle DraftDomain --- #
        # Do we already have an existing DraftDomain?
        _draft_domains = DraftDomain.objects.filter(name=domain_info.domain.name)
        if _draft_domains.count() > 1:
            raise Exception("Multiple DraftDomain objects exist")

        # Create or grab existing DraftDomain object
        _requested_domain: DraftDomain
        if _draft_domains.count() == 0:
            _requested_domain = DraftDomain(name=domain_info.domain.name)
            _requested_domain.save()
        else:
            _requested_domain = _draft_domains.get()

        # --- Handle DomainApplication --- #
        # Do we already have an existing DomainApplication?
        existing_application = DomainApplication.objects.filter(
            approved_domain=domain_info.domain,
            requested_domain=_requested_domain,
            creator=domain_info.creator
        )
        if existing_application.count() > 1:
            raise Exception("Multiple DomainApplication objects exist")

        # Create or grab existing DomainApplication
        desired_application: DomainApplication
        if existing_application.count() == 0:
            desired_application = DomainApplication(
                approved_domain=domain_info.domain,
                creator=domain_info.creator,
                status=DomainApplication.ACTION_NEEDED,
            )
            desired_application.save()
        elif existing_application.count() == 1:
            desired_application = existing_application.get()

        # --- Add to DomainInformation --- #
        domain_info.domain_application = desired_application
        domain_info.save()


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
