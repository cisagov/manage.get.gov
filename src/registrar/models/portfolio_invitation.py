"""People are invited by email to administer domains."""

import logging
from django.contrib.auth import get_user_model
from django.db import models
from django_fsm import FSMField, transition
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from .utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices  # type: ignore
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

    status = FSMField(
        choices=PortfolioInvitationStatus.choices,
        default=PortfolioInvitationStatus.INVITED,
        protected=True,  # can't alter state except through transition methods!
    )

    def __str__(self):
        return f"Invitation for {self.email} on {self.portfolio} is {self.status}"

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
        if self.portfolio_roles and len(self.portfolio_roles) > 0:
            user_portfolio_permission.roles = self.portfolio_roles
        if self.portfolio_additional_permissions and len(self.portfolio_additional_permissions) > 0:
            user_portfolio_permission.additional_permissions = self.portfolio_additional_permissions
        user_portfolio_permission.save()
