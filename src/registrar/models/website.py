from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class Website(TimeStampedModel):
    """Keep domain names in their own table so that applications can refer to
    many of them."""

    # domain names have strictly limited lengths, 255 characters is more than
    # enough.
    website = models.CharField(
        max_length=255,
        null=False,
        help_text="",
    )

    def __str__(self) -> str:
        return str(self.website)
