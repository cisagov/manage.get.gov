"""People are invited by email to administer domains."""

import logging

from django.contrib.auth import get_user_model
from django.db import models

from django_fsm import FSMField, transition  # type: ignore

from .utility.time_stamped_model import TimeStampedModel
from .user_domain_role import UserDomainRole
from django.forms import ValidationError


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
    
    def clean(self):
        existing_invitation = DomainInvitation.objects.filter(email__iexact=self.email, domain=self.domain)
        if existing_invitation:
            raise ValidationError(
                {"email": "An invitation this email and domain already exists"}
            )
    
    @transition(field="status", source=DomainInvitationStatus.INVITED, target=DomainInvitationStatus.CANCELED)
    def cancel_invitation(self):
        """When an invitation is canceled, change the status to canceled"""
        pass

    @transition(field="status", source=DomainInvitationStatus.CANCELED, target=DomainInvitationStatus.INVITED)
    def update_cancellation_status(self):
        """When an invitation is canceled but reinvited, update the status to invited"""
        pass
