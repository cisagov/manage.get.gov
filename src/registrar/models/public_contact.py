from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class PublicContact(TimeStampedModel):
    """Contact information intended to be published in WHOIS."""

    class ContactTypeChoices(models.TextChoices):
        """These are the types of contacts accepted by the registry."""

        REGISTRANT = "registrant", "Registrant"
        ADMINISTRATIVE = "administrative", "Administrative"
        TECHNICAL = "technical", "Technical"
        SECURITY = "security", "Security"

    contact_type = models.CharField(
        max_length=14,
        choices=ContactTypeChoices.choices,
        help_text="For which type of WHOIS contact"
    )

    uuid = models.TextField(
        null=True,
        blank=True,
        help_text="ID assigned by the registry"
    )
    has_edits = models.BooleanField(
        default=True,
        help_text="Whether edits have been made since last published"
    )
    domain = models.ForeignKey(
        "registrar.Domain",
        on_delete=models.PROTECT,
        related_name="contacts",
    )

    name = models.TextField(
        null=False,
        help_text="Contact's full name"
    )
    org = models.TextField(
        null=True,
        help_text="Contact's organization (null ok)"
    )
    street1 = models.TextField(
        null=False,
        help_text="Contact's street"
    )
    street2 = models.TextField(
        null=True,
        help_text="Contact's street (null ok)"
    )
    street3 = models.TextField(
        null=True,
        help_text="Contact's street (null ok)"
    )
    city = models.TextField(
        null=False,
        help_text="Contact's city"
    )
    sp = models.TextField(
        null=False,
        help_text="Contact's state or province"
    )
    pc = models.TextField(
        null=False,
        help_text="Contact's postal code"
    )
    cc = models.TextField(
        null=False,
        help_text="Contact's country code"
    )
    email = models.TextField(
        null=False,
        help_text="Contact's email address"
    )
    voice = models.TextField(
        null=False,
        help_text="Contact's phone number. Must be in ITU.E164.2005 format"
    )
    fax = models.TextField(
        null=True,
        help_text="Contact's fax number (null ok). Must be in ITU.E164.2005 format."
    )
    pw = models.TextField(
        null=False,
        help_text="Contact's authorization code. 16 characters minimum."
    )

    def __str__(self):
        return f"{self.name} <{self.email}>"
