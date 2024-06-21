from django.db import models

from .utility.time_stamped_model import TimeStampedModel
from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


class SeniorOfficial(TimeStampedModel):
    """
    Senior Official is a distinct Contact-like entity (NOT to be inherited
    from Contacts) developed for the unique role these individuals have in
    managing Portfolios.
    """

    first_name = models.CharField(
        null=False,
        blank=False,
        verbose_name="first name",
    )
    last_name = models.CharField(
        null=False,
        blank=False,
        verbose_name="last name",
    )
    title = models.CharField(
        null=False,
        blank=False,
        verbose_name="title / role",
    )
    phone = PhoneNumberField(
        null=True,
        blank=True,
    )

    def get_formatted_name(self):
        """Returns the contact's name in Western order."""
        names = [n for n in [self.first_name, self.last_name] if n]
        return " ".join(names) if names else "Unknown"

    def __str__(self):
        if self.first_name or self.last_name:
            return self.get_formatted_name()
        elif self.pk:
            return str(self.pk)
        else:
            return ""
