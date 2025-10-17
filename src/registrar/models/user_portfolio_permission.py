from django.db import models
from registrar.models.user_domain_role import UserDomainRole
from django.core.exceptions import ValidationError
from registrar.models.utility.portfolio_helper import (
    UserPortfolioPermissionChoices,
    UserPortfolioRoleChoices,
    DomainRequestPermissionDisplay,
    MemberPermissionDisplay,
    cleanup_after_portfolio_member_deletion,
    get_domain_requests_display,
    get_domain_requests_description_display,
    get_domains_display,
    get_domains_description_display,
    get_members_display,
    get_members_description_display,
    get_readable_roles,
    get_role_display,
    validate_user_portfolio_permission,
)
from .utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField


class UserPortfolioPermission(TimeStampedModel):
    """This is a linking table that connects a user with a role on a portfolio."""

    class Meta:
        unique_together = ["user", "portfolio"]

    PORTFOLIO_ROLE_PERMISSIONS = {
        UserPortfolioRoleChoices.ORGANIZATION_ADMIN: [
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
            UserPortfolioPermissionChoices.EDIT_REQUESTS,
            UserPortfolioPermissionChoices.VIEW_MEMBERS,
            UserPortfolioPermissionChoices.EDIT_MEMBERS,
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
        ],
        # NOTE: Check FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS before adding roles here.
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS,
        ],
    }

    # Determines which roles are forbidden for certain role types to possess.
    # Used to throw a ValidationError on clean() for UserPortfolioPermission and PortfolioInvitation.
    FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS = {
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            UserPortfolioPermissionChoices.EDIT_MEMBERS,
        ],
    }

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        "registrar.User",
        null=True,
        # when a user is deleted, permissions are too
        on_delete=models.CASCADE,
        related_name="portfolio_permissions",
    )

    portfolio = models.ForeignKey(
        "registrar.Portfolio",
        null=False,
        # when a portfolio is deleted, permissions are too
        on_delete=models.CASCADE,
        related_name="portfolio_users",
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

    # Invitation fields
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        null=True,
        help_text="Status of the portfolio permission invitation",
    )

    invited_by = models.ForeignKey(
        "registrar.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_portfolio_permissions",
        help_text="User who created the invitation",
    )

    invited_at = models.DateTimeField(null=True, blank=True)

    email = models.EmailField(null=True, blank=True)

    accepted_at = models.DateTimeField(null=True, blank=True)

    revoked_at = models.DateTimeField(null=True, blank=True)

    revocation_reason = models.TextField(null=True, blank=True)

    # End Invitation fields
    def __str__(self):
        readable_roles = []
        if self.roles:
            readable_roles = self.get_readable_roles()
        return f"{self.user}" f" <Roles: {', '.join(readable_roles)}>" if self.roles else ""

    def get_readable_roles(self):
        """Returns a readable list of self.roles"""
        return get_readable_roles(self.roles)

    def get_managed_domains_count(self):
        """Return the count of domains managed by the user for this portfolio."""
        # Filter the UserDomainRole model to get domains where the user has a manager role
        managed_domains = UserDomainRole.objects.filter(
            user=self.user, role=UserDomainRole.Roles.MANAGER, domain__domain_info__portfolio=self.portfolio
        ).count()
        return managed_domains

    def _get_portfolio_permissions(self):
        """
        Retrieve the permissions for the user's portfolio roles.
        """
        return self.get_portfolio_permissions(self.roles, self.additional_permissions)

    @classmethod
    def get_portfolio_permissions(cls, roles, additional_permissions, get_list=True):
        """Class method to return a list of permissions based on roles and addtl permissions.
        Params:
            roles => An array of roles
            additional_permissions => An array of additional_permissions
            get_list => If true, returns a list of perms. If false, returns a set of perms.
        """
        # Use a set to avoid duplicate permissions
        portfolio_permissions = set()
        if roles:
            for role in roles:
                portfolio_permissions.update(cls.PORTFOLIO_ROLE_PERMISSIONS.get(role, []))
        if additional_permissions:
            portfolio_permissions.update(additional_permissions)
        return list(portfolio_permissions) if get_list else portfolio_permissions

    @classmethod
    def get_domain_request_permission_display(cls, roles, additional_permissions):
        """Class method to return a readable string for domain request permissions"""
        # Tracks if they can view, create requests, or not do anything
        all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, additional_permissions)
        all_domain_perms = [
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
            UserPortfolioPermissionChoices.EDIT_REQUESTS,
        ]

        if all(perm in all_permissions for perm in all_domain_perms):
            return DomainRequestPermissionDisplay.VIEWER_REQUESTER
        elif UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS in all_permissions:
            return DomainRequestPermissionDisplay.VIEWER
        else:
            return DomainRequestPermissionDisplay.NONE

    @classmethod
    def get_member_permission_display(cls, roles, additional_permissions):
        """Class method to return a readable string for member permissions"""
        # Tracks if they can view, create requests, or not do anything.
        # This is different than get_domain_request_permission_display because member tracks
        # permissions slightly differently.
        all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, additional_permissions)
        if UserPortfolioPermissionChoices.EDIT_MEMBERS in all_permissions:
            return MemberPermissionDisplay.MANAGER
        elif UserPortfolioPermissionChoices.VIEW_MEMBERS in all_permissions:
            return MemberPermissionDisplay.VIEWER
        else:
            return MemberPermissionDisplay.NONE

    @classmethod
    def get_forbidden_permissions(cls, roles, additional_permissions):
        """Some permissions are forbidden for certain roles, like member.
        This checks for conflicts between the current permission list and forbidden perms."""

        # Get the portfolio permissions that the user currently possesses
        portfolio_permissions = set(cls.get_portfolio_permissions(roles, additional_permissions))

        # Get intersection of forbidden permissions across all roles.
        # This is because if you have roles ["admin", "member"], then they can have the
        # so called "forbidden" ones. But just member on their own cannot.
        # The solution to this is to only grab what is only COMMONLY "forbidden".
        # This will scale if we add more roles in the future.
        # This is thes same as applying the `&` operator across all sets for each role.
        common_forbidden_perms = (
            set.intersection(*[set(cls.FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS.get(role, [])) for role in roles])
            if roles
            else set()
        )

        # Check if the users current permissions overlap with any forbidden permissions
        # by getting the intersection between current user permissions, and forbidden ones.
        # This is the same as portfolio_permissions & common_forbidden_perms.
        return portfolio_permissions.intersection(common_forbidden_perms)

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
        is a "Requester" (can create and edit requests), a "Viewer" (can only view requests),
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

    def clean(self):
        """Extends clean method to perform additional validation, which can raise errors in django admin."""
        super().clean()
        # Ensure user is present for any non-invited status
        if self.status != self.Status.INVITED and self.user_id is None:
            raise ValidationError({"user": "User is required when status is not 'invited'."})
        # Ensure user exists before running further validation
        # In django admin, this clean method is called before form validation checks
        # for required fields. Since validation below requires user, skip if user does
        # not exist
        if self.user_id:
            validate_user_portfolio_permission(self)

    def delete(self, *args, **kwargs):

        user = self.user  # Capture the user before the instance is deleted
        portfolio = self.portfolio  # Capture the portfolio before the instance is deleted

        # Call the superclass delete method to actually delete the instance
        super().delete(*args, **kwargs)

        cleanup_after_portfolio_member_deletion(portfolio=portfolio, email=user.email, user=user)
