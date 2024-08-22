from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class AllowedEmails(TimeStampedModel):
    """
    AllowedEmails is a whitelist for email addresses that we can send to
    in non-production environments.
    """

    email = models.EmailField(
        unique=True,
        null=False,
        blank=False,
        max_length=320,
    )

    def __str__(self):
        return str(self.email)
