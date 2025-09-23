"""People are invited by email to administer domains."""

import logging
from django.db import models
from django_fsm import FSMField, transition
from django.contrib.auth import get_user_model
from registrar.models import DomainInvitation, UserPortfolioPermission
from .utility.portfolio_helper import (
    UserPortfolioPermissionChoices,
    UserPortfolioRoleChoices,
    cleanup_after_portfolio_member_deletion,
    get_domain_requests_description_display,
    get_domain_requests_display,
    get_domains_description_display,
    get_domains_display,
    get_members_description_display,
    get_members_display,
    get_readable_roles,
    get_role_display,
    validate_portfolio_invitation,
)  # type: ignore
from .utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField

logger = logging.getLogger(__name__)


class PortfolioInvitation(TimeStampedModel):
    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["status"]),
        ]

    # Constants for status field
    class PortfolioInvitationStatus(models.TextChoices):
        INVITED = "invited", "Invited"
        RETRIEVED = "retrieved", "Retrieved"

    email = models.EmailField(
        null=False,
        blank=False,
    )

    portfolio = models.ForeignKey(
        "registrar.Portfolio",
        on_delete=models.CASCADE,  # delete portfolio, then get rid of invitations
        null=False,
        related_name="portfolios",
    )

    roles = ArrayField(
        models.CharField(
            max_length=50,
            choices=UserPortfolioRoleChoices.choices,
        ),
        null=True,
        blank=True,
        help_text="Select one or more roles.",
    )

    additional_permissions = ArrayField(
        models.CharField(
            max_length=50,
            choices=UserPortfolioPermissionChoices.choices,
        ),
        null=True,
        blank=True,
        help_text="Select one or more additional permissions.",
    )

    status = FSMField(
        choices=PortfolioInvitationStatus.choices,
        default=PortfolioInvitationStatus.INVITED,
        protected=True,  # can't alter state except through transition methods!
    )

    def __str__(self):
        return f"Invitation for {self.email} on {self.portfolio} is {self.status}"

    def get_readable_roles(self):
        """Returns a readable list of self.roles"""
        return get_readable_roles(self.roles)

    def get_managed_domains_count(self):
        """Return the count of domain invitations managed by the invited user for this portfolio."""
        # Filter the UserDomainRole model to get domains where the user has a manager role
        managed_domains = DomainInvitation.objects.filter(
            email=self.email, domain__domain_info__portfolio=self.portfolio
        ).count()
        return managed_domains

    def get_portfolio_permissions(self):
        """
        Retrieve the permissions for the user's portfolio roles from the invite.
        """
        return UserPortfolioPermission.get_portfolio_permissions(self.roles, self.additional_permissions)

    @property
    def role_display(self):
        """
        Returns a human-readable display name for the user's role.

        Uses the `get_role_display` function to determine if the user is an "Admin",
        "Basic" member, or has no role assigned.

        Returns:
            str: The display name of the user's role.
        """
        return get_role_display(self.roles)

    @property
    def domains_display(self):
        """
        Returns a string representation of the user's domain access level.

        Uses the `get_domains_display` function to determine whether the user has
        "Viewer" access (can view all domains) or "Viewer, limited" access.

        Returns:
            str: The display name of the user's domain permissions.
        """
        return get_domains_display(self.roles, self.additional_permissions)

    @property
    def domains_description_display(self):
        """
        Returns a string description of the user's domain access level.

        Returns:
            str: The display name of the user's domain permissions description.
        """
        return get_domains_description_display(self.roles, self.additional_permissions)

    @property
    def domain_requests_display(self):
        """
        Returns a string representation of the user's access to domain requests.

        Uses the `get_domain_requests_display` function to determine if the user
        is a "requester" (can create and edit requests), a "Viewer" (can only view requests),
        or has "No access" to domain requests.

        Returns:
            str: The display name of the user's domain request permissions.
        """
        return get_domain_requests_display(self.roles, self.additional_permissions)

    @property
    def domain_requests_description_display(self):
        """
        Returns a string description of the user's access to domain requests.

        Returns:
            str: The display name of the user's domain request permissions description.
        """
        return get_domain_requests_description_display(self.roles, self.additional_permissions)

    @property
    def members_display(self):
        """
        Returns a string representation of the user's access to managing members.

        Uses the `get_members_display` function to determine if the user is a
        "Manager" (can edit members), a "Viewer" (can view members), or has "No access"
        to member management.

        Returns:
            str: The display name of the user's member management permissions.
        """
        return get_members_display(self.roles, self.additional_permissions)

    @property
    def members_description_display(self):
        """
        Returns a string description of the user's access to managing members.

        Returns:
            str: The display name of the user's member management permissions description.
        """
        return get_members_description_display(self.roles, self.additional_permissions)

    @transition(field="status", source=PortfolioInvitationStatus.INVITED, target=PortfolioInvitationStatus.RETRIEVED)
    def retrieve(self):
        """When an invitation is retrieved, create the corresponding permission.

        Raises:
            RuntimeError if no matching user can be found.
        """

        # get a user with this email address
        User = get_user_model()
        try:
            user = User.objects.get(email=self.email)
        except User.DoesNotExist:
            # should not happen because a matching user should exist before
            # we retrieve this invitation
            raise RuntimeError("Cannot find the user to retrieve this portfolio invitation.")

        # and create a role for that user on this portfolio
        user_portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio, user=user
        )
        if self.roles and len(self.roles) > 0:
            user_portfolio_permission.roles = self.roles
        if self.additional_permissions and len(self.additional_permissions) > 0:
            user_portfolio_permission.additional_permissions = self.additional_permissions
        user_portfolio_permission.save()

    def clean(self):
        """Extends clean method to perform additional validation, which can raise errors in django admin."""
        super().clean()
        validate_portfolio_invitation(self)

    def delete(self, *args, **kwargs):

        User = get_user_model()

        email = self.email  # Capture the email before the instance is deleted
        portfolio = self.portfolio  # Capture the portfolio before the instance is deleted

        # Call the superclass delete method to actually delete the instance
        super().delete(*args, **kwargs)

        if self.status == self.PortfolioInvitationStatus.INVITED:

            # Query the user by email
            users = User.objects.filter(email=email)

            if users.count() > 1:
                # This should never happen, log an error if more than one object is returned
                logger.error(f"Multiple users found with the same email: {email}")

            # Retrieve the first user, or None if no users are found
            user = users.first()

            cleanup_after_portfolio_member_deletion(portfolio=portfolio, email=email, user=user)
