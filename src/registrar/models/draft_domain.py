import logging

from django.db import models

from .utility.domain_helper import DomainHelper
from .utility.time_stamped_model import TimeStampedModel

logger = logging.getLogger(__name__)


class DraftDomain(TimeStampedModel, DomainHelper):
    """Store domain names which registrants have requested."""

    def __str__(self) -> str:
        return self.name

    name = models.CharField(
        max_length=253,
        blank=False,
        default=None,  # prevent saving without a value
        help_text="Fully qualified domain name",
    )

    draft_number = models.IntegerField(
        null=True,
        help_text="The draft number in the event a user doesn't save at this stage",
    )

    is_incomplete = models.BooleanField(default=False, help_text="Determines if this Draft is complete or not")

    def get_default_request_name(self):
        """Returns the draft name that would be used for applications if no name exists"""
        return f"New domain request {self.draft_number}"
