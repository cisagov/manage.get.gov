"""People are invited by email to administer domains."""

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from django_fsm import FSMField, transition  # type: ignore

from .utility.time_stamped_model import TimeStampedModel
from .user_domain_role import UserDomainRole


logger = logging.getLogger(__name__)


class DomainInvitation(TimeStampedModel):
    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["status"]),
        ]

    # Constants for status field
    class DomainInvitationStatus(models.TextChoices):
        INVITED = "invited", "Invited"
        RETRIEVED = "retrieved", "Retrieved"
        CANCELED = "canceled", "Canceled"

    email = models.EmailField(
        null=False,
        blank=False,
    )

    domain = models.ForeignKey(
        "registrar.Domain",
        on_delete=models.CASCADE,  # delete domain, then get rid of invitations
        null=False,
        related_name="invitations",
    )

    status = FSMField(
        choices=DomainInvitationStatus.choices,
        default=DomainInvitationStatus.INVITED,
        protected=True,  # can't alter state except through transition methods!
    )

    def __str__(self):
        return f"Invitation for {self.email} on {self.domain} is {self.status}"

    def clean(self):
        """Validate that retrieved invitations have corresponding UserDomainRole."""
        super().clean()

        # If status is RETRIEVED, there must be a corresponding UserDomainRole
        if self.status == self.DomainInvitationStatus.RETRIEVED:
            # Find the user by email (case-isensitive)
            User = get_user_model()
            try:
                user = User.objects.get(email__iexact=self.email)
            except User.DoesNotExist:
                raise ValidationError(
                    f"Cannot have status=RETRIEVED when user with email '{self.email}' does not exist. "
                    "Please cancel this invitation or ensure the user exists."
                )

            # Check if UserDomainROle exists for this user+domain
            role_exists = UserDomainRole.objects.filter(
                user=user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
            ).exists()

            if not role_exists:
                raise ValidationError(
                    f"Cannot have status=RETRIEVED when there is no corresponding UserDomainRole "
                    f"for user '{self.email}' on domain '{self.domain.name}'. "
                    "Please cancel this invitation or ensure the user is a domain manager."
                )

    @transition(field="status", source=DomainInvitationStatus.INVITED, target=DomainInvitationStatus.RETRIEVED)
    def retrieve(self):
        """When an invitation is retrieved, create the corresponding permission.

        Raises:
            RuntimeError if no matching user can be found.
        """

        # get a user with this email address
        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=self.email)
        except User.DoesNotExist:
            # should not happen because a matching user should exist before
            # we retrieve this invitation
            raise RuntimeError("Cannot find the user to retrieve this domain invitation.")

        # and create a role for that user on this domain
        _, created = UserDomainRole.objects.get_or_create(
            user=user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )
        if not created:
            # something strange happened and this role already existed when
            # the invitation was retrieved. Log that this occurred.
            logger.warn("Invitation %s was retrieved for a role that already exists.", self)

    @transition(field="status", source=DomainInvitationStatus.INVITED, target=DomainInvitationStatus.CANCELED)
    def cancel_invitation(self):
        """When an invitation is canceled, change the status to canceled"""
        pass

    @transition(field="status", source=DomainInvitationStatus.RETRIEVED, target=DomainInvitationStatus.CANCELED)
    def cancel_retrieved_invitation(self):
        """Cancel a retrieved invitation (used for cleaning up orphaned invitations)"""
        pass

    @transition(field="status", source=DomainInvitationStatus.CANCELED, target=DomainInvitationStatus.INVITED)
    def update_cancellation_status(self):
        """When an invitation is canceled but reinvited, update the status to invited"""
        pass
