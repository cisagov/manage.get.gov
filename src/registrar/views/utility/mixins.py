"""Permissions-related mixin classes."""

from django.contrib.auth.mixins import PermissionRequiredMixin

from registrar.models import (
    Domain,
    DomainApplication,
    DomainInvitation,
    DomainInformation,
    UserDomainRole,
)
import logging


logger = logging.getLogger(__name__)

class OrderableFieldsMixin:
    orderable_fk_fields = []

    def __new__(cls, *args, **kwargs):
        new_class = super().__new__(cls)
        for field, sort_field in cls.orderable_fk_fields:
            setattr(new_class, f'get_{field}', cls._create_orderable_field_method(field, sort_field))
        return new_class

    @classmethod
    def _create_orderable_field_method(cls, field, sort_field):
        def method(obj):
            attr = getattr(obj, field)
            return attr
        method.__name__ = f'get_{field}'
        method.admin_order_field = f'{field}__{sort_field}'
        method.short_description = field.replace('_', ' ').title()
        return method


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

        # test if domain in editable state
        if not self.in_editable_state(pk):
            return False

        if self.can_access_other_user_domains(pk):
            return True

        # user needs to have a role on the domain
        if not UserDomainRole.objects.filter(user=self.request.user, domain__id=pk).exists():
            return False

        # if we need to check more about the nature of role, do it here.
        return True

    def in_editable_state(self, pk):
        """Is the domain in an editable state"""

        requested_domain = None
        if Domain.objects.filter(id=pk).exists():
            requested_domain = Domain.objects.get(id=pk)

        # if domain is editable return true
        if requested_domain and requested_domain.is_editable():
            return True
        return False

    def can_access_other_user_domains(self, pk):
        """Checks to see if an authorized user (staff or superuser)
        can access a domain that they did not create or was invited to.
        """

        # Check if the user is permissioned...
        user_is_analyst_or_superuser = self.request.user.has_perm(
            "registrar.analyst_access_permission"
        ) or self.request.user.has_perm("registrar.full_access_permission")

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
            DomainApplication.ApplicationStatus.APPROVED,
            DomainApplication.ApplicationStatus.IN_REVIEW,
            DomainApplication.ApplicationStatus.REJECTED,
            DomainApplication.ApplicationStatus.ACTION_NEEDED,
            # Edge case - some domains do not have
            # a status or DomainInformation... aka a status of 'None'.
            # It is necessary to access those to correct errors.
            None,
        ]

        requested_domain = None
        if DomainInformation.objects.filter(id=pk).exists():
            requested_domain = DomainInformation.objects.get(id=pk)

        # if no domain information or application exist, the user
        # should be able to manage the domain; however, if domain information
        # and domain application exist, and application is not in valid status,
        # user should not be able to manage domain
        if (
            requested_domain
            and requested_domain.domain_application
            and requested_domain.domain_application.status not in valid_domain_statuses
        ):
            return False

        # Valid session keys exist,
        # the user is permissioned,
        # and it is in a valid status
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
        if not DomainApplication.objects.filter(creator=self.request.user, id=self.kwargs["pk"]).exists():
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
