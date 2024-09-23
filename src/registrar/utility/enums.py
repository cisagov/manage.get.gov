"""Used for holding various enums"""

from enum import Enum
from registrar.utility import StrEnum


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


class DefaultEmail(Enum):
    """Stores the string values of default emails

    Overview of emails:
    - PUBLIC_CONTACT_DEFAULT: "dotgov@cisa.dhs.gov"
    - LEGACY_DEFAULT: "registrar@dotgov.gov"
    """

    PUBLIC_CONTACT_DEFAULT = "dotgov@cisa.dhs.gov"
    LEGACY_DEFAULT = "registrar@dotgov.gov"


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

    # Portfolio
    REQUESTING_ENTITY = "organization_name"
    CURRENT_SITES = "current_sites"
    DOTGOV_DOMAIN = "dotgov_domain"
    PURPOSE = "purpose"
    ADDITIONAL_DETAILS = "additional_details"
    REQUIREMENTS = "requirements"
