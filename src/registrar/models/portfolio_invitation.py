"""People are invited by email to administer domains."""

import logging
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from django_fsm import FSMField, transition
from registrar.models import DomainInvitation
from registrar.utility.waffle import flag_is_active_for_user
from .utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices  # type: ignore
from .utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.forms import ValidationError


logger = logging.getLogger(__name__)


class PortfolioInvitation(TimeStampedModel):
    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["status"]),
        ]

        # Determine if we need this
        unique_together = [("email", "portfolio")]

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
        related_name="portfolio_invitations",
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
        UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
        return self.roles, self.additional_permissions)

    @transition(field="status", source=PortfolioInvitationStatus.INVITED, target=PortfolioInvitationStatus.RETRIEVED)
    def retrieve(self):
        """When an invitation is retrieved, create the corresponding permission.

        Raises:
            RuntimeError if no matching user can be found.
        """

        # get a user with this email address
        UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
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

        is_admin = UserPortfolioRoleChoices.ORGANIZATION_ADMIN in self.roles
        all_permissions = self.get_portfolio_permissions()
        if not is_admin:
            # Question: should we also check the edit perms?
            # TODO - need to display multiple validation errors at once
            if UserPortfolioPermissionChoices.VIEW_MEMBERS in all_permissions:
                raise ValidationError("View members cannot be assigned to non-admin roles.")
            
            if UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS:
                raise ValidationError("View all domains cannot be assigned to non-admin roles.")

        # Check if a user is set without accessing the related object.
        # TODO - revise this user check
        # get a user with this email address
        User = get_user_model()
        user = User.objects.filter(email=self.email).first()
        if not flag_is_active_for_user(user, "multiple_portfolios"):
            # TODO - need to display multiple validation errors
            UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
            existing_permissions = UserPortfolioPermission.objects.filter(user=user)
            existing_invitations = PortfolioInvitation.objects.exclude(id=self.id).filter(email=user.email)
            if existing_permissions.exists():
                raise ValidationError(
                    "This user is already assigned to a portfolio. "
                    "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
                )
            
            if existing_invitations.exists():
                raise ValidationError(
                    "This user is already assigned to a portfolio invitation. "
                    "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
                )
