import re
from django.core.validators import MaxLengthValidator
from django.core.exceptions import ValidationError

"""
Centralized character length "buckets" to keep server-side validation and
USWDS character-count UI in sync. Import and use like:

from registrar.validations import (
    TEXT_SHORT,
    TEXT_EXTENDED,
    TEXTAREA_LONG,
    TEXTAREA_SHORT,
    EMAIL_MAX,
    DOMAIN_LABEL,
    get_max_length_validator,
    get_max_length_attrs,
)

# Example:
# forms.CharField(
#     validators=[get_max_length_validator(TEXT_EXTENDED)],
#     widget=forms.TextInput(attrs=get_max_length_attrs(TEXT_EXTENDED)),
# )
"""

# Short single-line text inputs like first_name, last_name, city, urbanization, etc.
TEXT_SHORT = 50

# Extended single-line text inputs like address_line1/2, tribe_name, organization_name, titles, etc.
TEXT_EXTENDED = 100

# Multi-line textarea inputs like purpose, about, etc.
TEXTAREA_LONG = 1000

# Shorter textarea inputs like no_other_contacts_rationale
TEXTAREA_SHORT = 500

# Email maximum length per standards, like SeniorOfficialForm.email, etc.
EMAIL_MAX = 320

# DNS single label max length per standards, like requested_domain, alternative_domain, etc.
DOMAIN_LABEL = 63


# For system level validation
def get_max_length_validator(limit: int) -> MaxLengthValidator:
    return MaxLengthValidator(limit, message=f"Response must be no more than {limit} characters.")


# For use by the USWDS framework to display the max length to the user
def get_max_length_attrs(limit: int) -> dict[str, str]:
    return {"maxlength": str(limit)}

# For use on DNS record names
DNS_LABEL_REGEX = re.compile(r"^[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")

def validate_dns_name(value: str) -> None:
    """
    Validates a DNS record name (single label, excluding the root '@')
    """
    if not DNS_LABEL_REGEX.match(value):
        raise ValidationError(
            "DNS record name must be 63 characters or fewer, start with a letter, "
            "end with a letter or digit, and contain only letters, digits, or hyphens."
        )
