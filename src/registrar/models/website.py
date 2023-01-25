from django.apps import apps
from django.core.exceptions import ValidationError
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

    @property
    def sld(self):
        """Get or set the second level domain string."""
        return self.website.split(".")[0]

    @sld.setter
    def sld(self, value: str):
        Domain = apps.get_model("registrar.Domain")
        parts = self.website.split(".")
        tld = parts[1] if len(parts) > 1 else ""
        if Domain.string_could_be_domain(f"{value}.{tld}"):
            self.website = f"{value}.{tld}"
        else:
            raise ValidationError("%s is not a valid second level domain" % value)

    @property
    def tld(self):
        """Get or set the top level domain string."""
        parts = self.website.split(".")
        return parts[1] if len(parts) > 1 else ""

    @tld.setter
    def tld(self, value: str):
        Domain = apps.get_model("registrar.Domain")
        sld = self.website.split(".")[0]
        if Domain.string_could_be_domain(f"{sld}.{value}"):
            self.website = f"{sld}.{value}"
        else:
            raise ValidationError("%s is not a valid top level domain" % value)

    def __str__(self) -> str:
        return str(self.website)
