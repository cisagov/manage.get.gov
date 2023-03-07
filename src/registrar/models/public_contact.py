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

    contact_type = models.CharField(max_length=14, choices=ContactTypeChoices.choices)

    # contact's full name
    name = models.TextField(null=False)
    # contact's organization (null ok)
    org = models.TextField(null=True)
    # contact's street
    street1 = models.TextField(null=False)
    # contact's street (null ok)
    street2 = models.TextField(null=True)
    # contact's street (null ok)
    street3 = models.TextField(null=True)
    # contact's city
    city = models.TextField(null=False)
    # contact's state or province
    sp = models.TextField(null=False)
    # contact's postal code
    pc = models.TextField(null=False)
    # contact's country code
    cc = models.TextField(null=False)
    # contact's email address
    email = models.TextField(null=False)
    # contact's phone number
    # Must be in ITU.E164.2005 format
    voice = models.TextField(null=False)
    # contact's fax number (null ok)
    # Must be in ITU.E164.2005 format
    fax = models.TextField(null=True)
    # contact's authorization code
    # 16 characters minium
    pw = models.TextField(null=False)

    def __str__(self):
        return f"{self.name} <{self.email}>"
