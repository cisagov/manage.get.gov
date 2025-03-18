"""People are invited by email to administer domains."""

import logging
from django.db import models
from .utility.state_controlled_model import StateControlledModel

logger = logging.getLogger(__name__)


class DomainInvitation(StateControlledModel):
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

    status = models.CharField(
        choices=DomainInvitationStatus.choices,
        default=DomainInvitationStatus.INVITED,
    )

    def __str__(self):
        return f"Invitation for {self.email} on {self.domain} is {self.status}"
