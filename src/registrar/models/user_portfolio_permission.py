from django.db import models
from django.forms import ValidationError
from registrar.utility.waffle import flag_is_active_for_user
from registrar.models import UserDomainRole
from registrar.models.utility.portfolio_helper import (
    UserPortfolioPermissionChoices,
    UserPortfolioRoleChoices,
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
            UserPortfolioPermissionChoices.VIEW_MEMBERS,
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            # Domain: field specific permissions
            UserPortfolioPermissionChoices.VIEW_SUBORGANIZATION,
            UserPortfolioPermissionChoices.EDIT_SUBORGANIZATION,
        ],
        # NOTE: We currently forbid members from posessing view_members or view_all_domains.
        # If those are added here, clean() will throw errors.
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
        ],
    }

    # Determines which roles are forbidden for certain role types to possess.
    FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS = {
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            UserPortfolioPermissionChoices.VIEW_MEMBERS,
            UserPortfolioPermissionChoices.EDIT_MEMBERS,
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
        ],
    }

    user = models.ForeignKey(
        "registrar.User",
        null=False,
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

    def __str__(self):
        readable_roles = []
        if self.roles:
            readable_roles = self.get_readable_roles()
        return f"{self.user}" f" <Roles: {', '.join(readable_roles)}>" if self.roles else ""

    def get_readable_roles(self):
        """Returns a readable list of self.roles"""
        readable_roles = []
        if self.roles:
            readable_roles = sorted(
                [UserPortfolioRoleChoices.get_user_portfolio_role_label(role) for role in self.roles]
            )
        return readable_roles

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
    def get_portfolio_permissions(cls, roles, additional_permissions):
        """Class method to return a list of permissions based on roles and addtl permissions"""
        # Use a set to avoid duplicate permissions
        portfolio_permissions = set()
        if roles:
            for role in roles:
                portfolio_permissions.update(cls.PORTFOLIO_ROLE_PERMISSIONS.get(role, []))
        if additional_permissions:
            portfolio_permissions.update(additional_permissions)
        return list(portfolio_permissions)

    @classmethod
    def get_forbidden_permissions(cls, roles, additional_permissions):
        """Some permissions are forbidden for certain roles, like member.
        This checks for conflicts between the role and additional_permissions."""
        portfolio_permissions = set(cls.get_portfolio_permissions(roles, additional_permissions))

        # Get intersection of forbidden permissions across all roles.
        # This is because if you have roles ["admin", "member"], then they can have the
        # so called "forbidden" ones. But just member on their own cannot.
        # The solution to this is to only grab what is only COMMONLY "forbidden".
        # This will scale if we add more roles in the future.
        common_forbidden_perms = set.intersection(
            *(set(cls.FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS.get(role, [])) for role in roles)
        )

        # Check if the users current permissions overlap with any forbidden permissions
        bad_perms = portfolio_permissions & common_forbidden_perms
        return bad_perms

    def clean(self):
        """Extends clean method to perform additional validation, which can raise errors in django admin."""
        super().clean()
        validate_user_portfolio_permission(self)
