from django.db import models
from django.forms import ValidationError
from registrar.utility.waffle import flag_is_active_for_user
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

    def _get_portfolio_permissions(self):
        """
        Retrieve the permissions for the user's portfolio roles.
        """
        # Use a set to avoid duplicate permissions
        portfolio_permissions = set()

        if self.roles:
            for role in self.roles:
                portfolio_permissions.update(self.PORTFOLIO_ROLE_PERMISSIONS.get(role, []))

        if self.additional_permissions:
            portfolio_permissions.update(self.additional_permissions)

        return list(portfolio_permissions)

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
