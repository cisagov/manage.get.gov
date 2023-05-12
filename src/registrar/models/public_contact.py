from datetime import datetime
from random import choices
from string import ascii_uppercase, ascii_lowercase, digits

from django.db import models

from .utility.time_stamped_model import TimeStampedModel


def get_id():
    """Generate a 16 character registry ID with a low probability of collision."""
    day = datetime.today().strftime("%A")[:2]
    rand = "".join(
        choices(ascii_uppercase + ascii_lowercase + digits, k=14)  # nosec B311
    )
    return f"{day}{rand}"


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
        help_text="For which type of WHOIS contact",
    )
    registry_id = models.CharField(
        max_length=16,
        default=get_id,
        null=False,
        help_text="Auto generated ID to track this contact in the registry",
    )

    has_edits = models.BooleanField(
        default=True, help_text="Whether edits have been made since last published"
    )
    domain = models.ForeignKey(
        "registrar.Domain",
        on_delete=models.PROTECT,
        related_name="contacts",
    )

    name = models.TextField(null=False, help_text="Contact's full name")
    org = models.TextField(null=True, help_text="Contact's organization (null ok)")
    street1 = models.TextField(null=False, help_text="Contact's street")
    street2 = models.TextField(null=True, help_text="Contact's street (null ok)")
    street3 = models.TextField(null=True, help_text="Contact's street (null ok)")
    city = models.TextField(null=False, help_text="Contact's city")
    sp = models.TextField(null=False, help_text="Contact's state or province")
    pc = models.TextField(null=False, help_text="Contact's postal code")
    cc = models.TextField(null=False, help_text="Contact's country code")
    email = models.TextField(null=False, help_text="Contact's email address")
    voice = models.TextField(
        null=False, help_text="Contact's phone number. Must be in ITU.E164.2005 format"
    )
    fax = models.TextField(
        null=True,
        help_text="Contact's fax number (null ok). Must be in ITU.E164.2005 format.",
    )
    pw = models.TextField(
        null=False, help_text="Contact's authorization code. 16 characters minimum."
    )

    @classmethod
    def get_default_registrant(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            registry_id="CISA00REGISTRANT",
            name="CSD/CB – Attn: Cameron Dixon",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="CISA – NGR STOP 0645",
            street2="1110 N. Glebe Rd.",
            city="Arlington",
            sp="VA",
            pc="20598-0645",
            cc="US",
            email="dotgov@cisa.dhs.gov",
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    @classmethod
    def get_default_administrative(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE,
            registry_id="CISA0000000ADMIN",
            name="Program Manager",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="4200 Wilson Blvd.",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email="dotgov@cisa.dhs.gov",
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    @classmethod
    def get_default_technical(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.TECHNICAL,
            registry_id="CISA00000000TECH",
            name="Registry Customer Service",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="4200 Wilson Blvd.",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email="dotgov@cisa.dhs.gov",
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    @classmethod
    def get_default_security(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.SECURITY,
            registry_id="CISA0000SECURITY",
            name="Registry Customer Service",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="4200 Wilson Blvd.",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email="dotgov@cisa.dhs.gov",
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    def __str__(self):
        return f"{self.name} <{self.email}>"
