import logging
from datetime import datetime
from random import choices
from string import ascii_uppercase, ascii_lowercase, digits

from django.db import models

from registrar.utility.enums import DefaultEmail

from .utility.time_stamped_model import TimeStampedModel

logger = logging.getLogger(__name__)


def get_id():
    """Generate a 16 character registry ID with a low probability of collision."""
    day = datetime.today().strftime("%A")[:2]
    rand = "".join(choices(ascii_uppercase + ascii_lowercase + digits, k=14))  # nosec B311
    return f"{day}{rand}"


class PublicContact(TimeStampedModel):
    """Contact information intended to be published in WHOIS."""

    class Meta:
        """Contains meta info about this class"""

        # Creates a composite primary key with these fields.
        # We can share the same registry id, but only if the contact type is
        # different or if the domain is different.
        # For instance - we don't desire to have two admin contacts with the same id
        # on the same domain.
        unique_together = [("contact_type", "registry_id", "domain")]

    class ContactTypeChoices(models.TextChoices):
        """These are the types of contacts accepted by the registry."""

        REGISTRANT = "registrant", "Registrant"
        ADMINISTRATIVE = "admin", "Administrative"
        TECHNICAL = "tech", "Technical"
        SECURITY = "security", "Security"

    def save(self, *args, **kwargs):
        """Save to the registry and also locally in the registrar database."""
        skip_epp_save = kwargs.pop("skip_epp_save", False)
        if hasattr(self, "domain") and not skip_epp_save:
            match self.contact_type:
                case PublicContact.ContactTypeChoices.REGISTRANT:
                    self.domain.registrant_contact = self
                case PublicContact.ContactTypeChoices.ADMINISTRATIVE:
                    self.domain.administrative_contact = self
                case PublicContact.ContactTypeChoices.TECHNICAL:
                    self.domain.technical_contact = self
                case PublicContact.ContactTypeChoices.SECURITY:
                    self.domain.security_contact = self
        super().save(*args, **kwargs)

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
    domain = models.ForeignKey(
        "registrar.Domain",
        on_delete=models.PROTECT,
        related_name="contacts",
    )

    name = models.CharField(null=False, help_text="Contact's full name")
    org = models.CharField(null=True, blank=True, help_text="Contact's organization (null ok)")
    street1 = models.CharField(null=False, help_text="Contact's street")
    street2 = models.CharField(null=True, blank=True, help_text="Contact's street (null ok)")
    street3 = models.CharField(null=True, blank=True, help_text="Contact's street (null ok)")
    city = models.CharField(null=False, help_text="Contact's city")
    sp = models.CharField(null=False, help_text="Contact's state or province")
    pc = models.CharField(null=False, help_text="Contact's postal code")
    cc = models.CharField(null=False, help_text="Contact's country code")
    email = models.EmailField(null=False, help_text="Contact's email address", max_length=320)
    voice = models.CharField(null=False, help_text="Contact's phone number. Must be in ITU.E164.2005 format")
    fax = models.CharField(
        null=True,
        blank=True,
        help_text="Contact's fax number (null ok). Must be in ITU.E164.2005 format.",
    )
    pw = models.CharField(null=False, help_text="Contact's authorization code. 16 characters minimum.")

    @classmethod
    def get_default_registrant(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            registry_id=get_id(),
            name="CSD/CB – Attn: .gov TLD",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="1110 N. Glebe Rd",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email=DefaultEmail.PUBLIC_CONTACT_DEFAULT,
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    @classmethod
    def get_default_administrative(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE,
            registry_id=get_id(),
            name="CSD/CB – Attn: .gov TLD",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="1110 N. Glebe Rd",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email=DefaultEmail.PUBLIC_CONTACT_DEFAULT,
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    @classmethod
    def get_default_technical(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.TECHNICAL,
            registry_id=get_id(),
            name="CSD/CB – Attn: .gov TLD",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="1110 N. Glebe Rd",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email=DefaultEmail.PUBLIC_CONTACT_DEFAULT,
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    @classmethod
    def get_default_security(cls):
        return cls(
            contact_type=PublicContact.ContactTypeChoices.SECURITY,
            registry_id=get_id(),
            name="CSD/CB – Attn: .gov TLD",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="1110 N. Glebe Rd",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email=DefaultEmail.PUBLIC_CONTACT_DEFAULT,
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )

    @classmethod
    def get_max_id_length(cls):
        return cls._meta.get_field("registry_id").max_length

    def __str__(self):
        return self.registry_id
