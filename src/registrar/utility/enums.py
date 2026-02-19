"""Used for holding various enums"""

from enum import Enum
from registrar.utility import StrEnum
from django.core.validators import validate_ipv4_address, validate_ipv6_address
from django.db.models import TextChoices


class ValidationReturnType(Enum):
    """Determines the return value of the validate_and_handle_errors class"""

    JSON_RESPONSE = "JSON_RESPONSE"
    FORM_VALIDATION_ERROR = "FORM_VALIDATION_ERROR"


class LogCode(Enum):
    """Stores the desired log severity

    Overview of error codes:
    - 1 ERROR
    - 2 WARNING
    - 3 INFO
    - 4 DEBUG
    - 5 DEFAULT
    """

    ERROR = 1
    WARNING = 2
    INFO = 3
    DEBUG = 4
    DEFAULT = 5


class DefaultEmail(StrEnum):
    """Stores the string values of default emails

    Overview of emails:
    - PUBLIC_CONTACT_DEFAULT: "help@get.gov"
    - OLD_PUBLIC_CONTACT_DEFAULT: "dotgov@cisa.dhs.gov"
    - LEGACY_DEFAULT: "registrar@dotgov.gov"
    """

    PUBLIC_CONTACT_DEFAULT = "help@get.gov"
    # We used to use this email for default public contacts.
    # This is retained for data correctness, but it will be phased out.
    # help@get.gov is the current email that we use for these now.
    OLD_PUBLIC_CONTACT_DEFAULT = "dotgov@cisa.dhs.gov"
    LEGACY_DEFAULT = "registrar@dotgov.gov"

    @classmethod
    def get_all_emails(cls):
        return [email for email in cls]


class DefaultUserValues(StrEnum):
    """Stores default values for a default user.

    Overview of defaults:
    - SYSTEM: "System" <= Default username
    - UNRETRIEVED: "Unretrieved" <= Default email state
    """

    HELP_EMAIL = "help@get.gov"
    SYSTEM = "System"
    UNRETRIEVED = "Unretrieved"


class Step(StrEnum):
    """
    Names for each page of the domain request wizard.

    As with Django's own `TextChoices` class, steps will
    appear in the order they are defined. (Order matters.)
    """

    # Non-Portfolio
    ORGANIZATION_TYPE = "generic_org_type"
    TRIBAL_GOVERNMENT = "tribal_government"
    ORGANIZATION_FEDERAL = "organization_federal"
    ORGANIZATION_ELECTION = "organization_election"
    ORGANIZATION_CONTACT = "organization_contact"
    ABOUT_YOUR_ORGANIZATION = "about_your_organization"
    SENIOR_OFFICIAL = "senior_official"
    CURRENT_SITES = "current_sites"
    DOTGOV_DOMAIN = "dotgov_domain"
    PURPOSE = "purpose"
    OTHER_CONTACTS = "other_contacts"
    ADDITIONAL_DETAILS = "additional_details"
    REQUIREMENTS = "requirements"
    REVIEW = "review"


class PortfolioDomainRequestStep(StrEnum):
    """
    Names for each page of the portfolio domain request wizard.

    As with Django's own `TextChoices` class, steps will
    appear in the order they are defined. (Order matters.)
    """

    # NOTE: Append portfolio_ when customizing a view for portfolio.
    # By default, these will redirect to the normal request flow views.
    # After creating a new view, you will need to add this to urls.py.
    REQUESTING_ENTITY = "portfolio_requesting_entity"
    DOTGOV_DOMAIN = "dotgov_domain"
    PURPOSE = "purpose"
    ADDITIONAL_DETAILS = "portfolio_additional_details"
    REQUIREMENTS = "requirements"
    REVIEW = "review"


class RecordTypes(TextChoices):
    A = "A", "A"
    AAAA = "AAAA", "AAAA"
    # CNAME = "CNAME", "CNAME"
    # MX = "MX", "MX"
    # TXT = "TXT", "TXT"

    @property
    def field_label(self) -> str:
        return {
            RecordTypes.A: "IPv4 address",
            RecordTypes.AAAA: "IPv6 address",
            # RecordTypes.CNAME: "Target hostname",
            # RecordTypes.MX: "Mail server",
            # RecordTypes.TXT: "Text content",
        }[self]

    @property
    def help_text(self) -> str:
        return {
            RecordTypes.A: "Example: 192.0.2.10",
            RecordTypes.AAAA: "Example: 2001:db8::1",
            # RecordTypes.CNAME: "Example: example.com",
            # RecordTypes.MX: "Example: mail.example.com",
            # RecordTypes.TXT: "Example: v=spf1 include:example.com ~all",
        }[self]

    @property
    def validator(self):
        return {
            RecordTypes.A: validate_ipv4_address,
            RecordTypes.AAAA: validate_ipv6_address,
        }.get(self)

    @property
    def error_message(self) -> str:
        return {
            RecordTypes.A: "Enter a valid IPv4 address using numbers and periods.",
            RecordTypes.AAAA: "Enter a valid IPv6 address using numbers and colons.",
        }.get(self, "Enter a valid value.")
