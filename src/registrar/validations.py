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

# Full FQDN max length per RFC 1035
MX_CONTENT_MAX_LENGTH = 253


# For system level validation
def get_max_length_validator(limit: int) -> MaxLengthValidator:
    return MaxLengthValidator(limit, message=f"Response must be no more than {limit} characters.")


# For use by the USWDS framework to display the max length to the user
def get_max_length_attrs(limit: int) -> dict[str, str]:
    return {"maxlength": str(limit)}


# For use on DNS record names
DNS_NAME_FIELD_REGEX = re.compile(r"^[a-zA-Z0-9.-]+$")


def validate_dns_name(name: str) -> None:
    """
    Validates a DNS record name (single label, excluding the root '@')
    """
    if name == "@":
        return

    if " " in name:
        raise ValidationError("Enter the DNS name without any spaces.")

    if not DNS_NAME_FIELD_REGEX.fullmatch(name):
        raise ValidationError("Enter a name using only letters, numbers, hyphens, periods, or the @ symbol.")

    if len(name) > DOMAIN_LABEL:
        raise ValidationError("Name must be no more than 63 characters.")

    if not name[0].isalpha() or not name[-1].isalnum():
        raise ValidationError("Enter a name that begins with a letter and ends with a letter or number.")


def _check_has_surrounding_quotes(content: str) -> bool:
    double_quote = '"'

    # check if string begins and ends with a quote
    first_item_char_is_double_quote = content[0] == double_quote
    last_item_is_double_quote = content[len(content) - 1] == double_quote

    return first_item_char_is_double_quote and last_item_is_double_quote

def check_has_valid_quotes(content: str) -> bool:
    double_quote = '"'
    quote_count = content.count(double_quote)

    # check if string begins and ends with a quote or no quote at all
    first_item_char_is_double_quote = content[0] == double_quote
    last_item_is_double_quote = content[len(content) - 1] == double_quote

    return quote_count % 2 != 0 or first_item_char_is_double_quote != last_item_is_double_quote


def validate_txt_content(content: str) -> None:

    if check_has_valid_quotes(content):
        raise ValidationError(
            'Enter content using quotation marks at the beginning and end.'
        )

    has_surrounding_quotes = _check_has_surrounding_quotes(content)
    if has_surrounding_quotes:
        # Remove the surrounding quotes for length validation
        content = content[1:-1]

    if len(content) > 4080:
        raise ValidationError("Content must be no more than 4080 characters.")


def validate_mx_content(content: str) -> None:
    """
    Validates an MX record's mail server hostname.
    """
    if " " in content:
        raise ValidationError("Enter the mail server without any spaces.")

    if len(content) > MX_CONTENT_MAX_LENGTH:
        raise ValidationError("Name must be no more than 253 characters.")

# Add this here temporarily before creating a cleaners.py file to hold any future cleaning functions that are needed for DNS record content or other fields. This is for any transformations that need to be applied to the content in addition to validation, such as ensuring TXT records are properly quoted.
def clean_txt_content(content: str) -> str:
        """Clean the content field for TXT records to ensure it is enclosed in quotes."""
        if content and not (content.startswith('"') and content.endswith('"')):
            return f'"{content}"'
        return content