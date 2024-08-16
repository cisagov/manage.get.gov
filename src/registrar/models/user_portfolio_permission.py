from django.db import models
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from .utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField


class UserPortfolioPermission(TimeStampedModel):
    """This is a linking table that connects a user with a role on a portfolio."""

    class Meta:
        unique_together = ["user", "portfolio"]

    PORTFOLIO_ROLE_PERMISSIONS = {
        UserPortfolioRoleChoices.ORGANIZATION_ADMIN: [
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
            UserPortfolioPermissionChoices.VIEW_MEMBER,
            UserPortfolioPermissionChoices.EDIT_MEMBER,
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
            UserPortfolioPermissionChoices.EDIT_REQUESTS,
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            # Domain: field specific permissions
            UserPortfolioPermissionChoices.VIEW_SUBORGANIZATION,
            UserPortfolioPermissionChoices.EDIT_SUBORGANIZATION,
        ],
        UserPortfolioRoleChoices.ORGANIZATION_ADMIN_READ_ONLY: [
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
            UserPortfolioPermissionChoices.VIEW_MEMBER,
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            # Domain: field specific permissions
            UserPortfolioPermissionChoices.VIEW_SUBORGANIZATION,
        ],
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
        ],
    }

    user = models.ForeignKey(
        "registrar.User",
        null=False,
        # when a portfolio is deleted, permissions are too
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

    portfolio_roles = ArrayField(
        models.CharField(
            max_length=50,
            choices=UserPortfolioRoleChoices.choices,
        ),
        null=True,
        blank=True,
        help_text="Select one or more roles.",
    )

    portfolio_additional_permissions = ArrayField(
        models.CharField(
            max_length=50,
            choices=UserPortfolioPermissionChoices.choices,
        ),
        null=True,
        blank=True,
        help_text="Select one or more additional permissions.",
    )

    def __str__(self):
        return (
            f"User '{self.user}' on Portfolio '{self.portfolio}' " 
            f"<Roles: {self.portfolio_roles}>"
        )

    def _get_portfolio_permissions(self):
        """
        Retrieve the permissions for the user's portfolio roles.
        """
        # Use a set to avoid duplicate permissions
        portfolio_permissions = set()

        if self.portfolio_roles:
            for role in self.portfolio_roles:
                portfolio_permissions.update(self.PORTFOLIO_ROLE_PERMISSIONS.get(role, []))

        if self.portfolio_additional_permissions:
            portfolio_permissions.update(self.portfolio_additional_permissions)

        return list(portfolio_permissions)
