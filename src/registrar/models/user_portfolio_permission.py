from django.db import models
from django.forms import ValidationError
from registrar.models.user_domain_role import UserDomainRole
from registrar.utility.waffle import flag_is_active_for_user
from registrar.models.utility.portfolio_helper import (
    UserPortfolioPermissionChoices,
    UserPortfolioRoleChoices,
    DomainRequestPermissionDisplay,
    MemberPermissionDisplay,
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
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            # Domain: field specific permissions
            UserPortfolioPermissionChoices.VIEW_SUBORGANIZATION,
            UserPortfolioPermissionChoices.EDIT_SUBORGANIZATION,
        ],
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
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

    def clean(self):
        """Extends clean method to perform additional validation, which can raise errors in django admin."""
        super().clean()

        # Check if portfolio is set without accessing the related object.
        has_portfolio = bool(self.portfolio_id)
        if not has_portfolio and self._get_portfolio_permissions():
            raise ValidationError("When portfolio roles or additional permissions are assigned, portfolio is required.")

        if has_portfolio and not self._get_portfolio_permissions():
            raise ValidationError("When portfolio is assigned, portfolio roles or additional permissions are required.")

        # Check if a user is set without accessing the related object.
        has_user = bool(self.user_id)
        if has_user:
            existing_permission_pks = UserPortfolioPermission.objects.filter(user=self.user).values_list(
                "pk", flat=True
            )
            if (
                not flag_is_active_for_user(self.user, "multiple_portfolios")
                and existing_permission_pks.exists()
                and self.pk not in existing_permission_pks
            ):
                raise ValidationError(
                    "This user is already assigned to a portfolio. "
                    "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
                )
