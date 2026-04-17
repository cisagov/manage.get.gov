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
DNS_NAME_MAX_LENGTH = 253

# Full FQDN max length per RFC 1035
MX_CONTENT_MAX_LENGTH = 253


# For system level validation
def get_max_length_validator(limit: int) -> MaxLengthValidator:
    return MaxLengthValidator(limit, message=f"Response must be no more than {limit} characters.")


# For use by the USWDS framework to display the max length to the user
def get_max_length_attrs(limit: int) -> dict[str, str]:
    return {"maxlength": str(limit)}


# For use on DNS record names
DNS_NAME_FORMAT_ERROR_MESSAGE = "Enter the name without using parentheses, colons, or semicolons."
DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE = "Enter the name without using consecutive periods."
DNS_NAME_LEADING_TRAILING_DOT_ERROR_MESSAGE = "Enter the name without using consecutive periods."
DNS_NAME_HYPHEN_ERROR_MESSAGE = "Enter the name without using hyphens at the start or end of a label."
DNS_NAME_LENGTH_ERROR_MESSAGE = (
    "Labels must be no more than 63 characters. "
    "Full name (including labels, domain, and period) must be no more than 253 characters."
)
DNS_NAME_SPACES_ERROR_MESSAGE = "Enter the DNS name without any spaces."
DNS_NAME_INVALID_CHARS = frozenset("@():;")

# For use on DNS record fields outside of name
DNS_RECORD_NAME_REQUIRED_ERROR_MESSAGE = "Enter the name of this record."
DNS_RECORD_CONTENT_REQUIRED_ERROR_MESSAGE = "Enter the content for this record."
DNS_RECORD_PRIORITY_REQUIRED_ERROR_MESSAGE = "Enter a priority for this record."
DNS_RECORD_PRIORITY_RANGE_ERROR_MESSAGE = "Enter a priority number between 0-65535."
MX_CONTENT_SPACES_ERROR_MESSAGE = "Enter the mail server without any spaces."


def _validate_dns_name_structure(name: str) -> None:
    """Reject empty labels created by consecutive, leading, or trailing dots."""
    if ".." in name:
        raise ValidationError(DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE)
    if name.startswith(".") or name.endswith("."):
        raise ValidationError(DNS_NAME_LEADING_TRAILING_DOT_ERROR_MESSAGE)


def _validate_dns_name_characters(name: str) -> None:
    """Reject characters explicitly disallowed by the AC (@ ( ) : ;).
    The apex '@' is handled earlier in validate_dns_name; any remaining '@' is invalid."""
    if any(ch in DNS_NAME_INVALID_CHARS for ch in name):
        raise ValidationError(DNS_NAME_FORMAT_ERROR_MESSAGE)


def _validate_dns_name_length(name: str) -> None:
    """Enforce the total DNS name length limit."""
    if len(name) > DNS_NAME_MAX_LENGTH:
        raise ValidationError(DNS_NAME_LENGTH_ERROR_MESSAGE)


def _get_non_wildcard_dns_name_labels(name: str) -> list[str]:
    """Return DNS labels that require per-label validation."""
    return [label for label in name.split(".") if label != "*"]


def _validate_dns_name_label_length(label: str) -> None:
    """Enforce the per-label DNS length limit."""
    if len(label) > DOMAIN_LABEL:
        raise ValidationError(DNS_NAME_LENGTH_ERROR_MESSAGE)


def _validate_dns_name_label_hyphen_placement(label: str) -> None:
    """Reject labels that begin or end with a hyphen."""
    if label.startswith("-") or label.endswith("-"):
        raise ValidationError(DNS_NAME_HYPHEN_ERROR_MESSAGE)


def _validate_dns_name_label(label: str) -> None:
    """Apply all per-label DNS name validations."""
    _validate_dns_name_label_length(label)
    _validate_dns_name_label_hyphen_placement(label)


def _validate_dns_name_labels(name: str) -> None:
    """Validate each label's length and hyphen placement."""
    for label in _get_non_wildcard_dns_name_labels(name):
        _validate_dns_name_label(label)


def validate_dns_name(name: str) -> None:
    """
    Validates a DNS record name. Handles both relative names (e.g., 'www') and
    fully qualified names (e.g., 'www.example.gov').

    Normalizes to lowercase and validates:
    - No spaces
    - Valid characters only (letters, numbers, hyphens, periods, @ for apex)
    - No consecutive dots
    - No leading/trailing dots
    - No hyphens at start/end of labels
    - Per-label max 63 characters
    - Total max 253 characters
    """
    if not name:
        return

    # Normalize to lowercase
    name = name.lower()

    # Special case: @ is valid (zone apex)
    if name == "@":
        return

    # Check for spaces
    if " " in name:
        raise ValidationError(DNS_NAME_SPACES_ERROR_MESSAGE)

    _validate_dns_name_structure(name)
    _validate_dns_name_characters(name)
    _validate_dns_name_length(name)
    _validate_dns_name_labels(name)


def validate_dns_name_fqdn_length(name: str, zone_name: str | None) -> None:
    """
    Enforce the 253-character limit on the fully qualified DNS name.

    The zone name is appended when the entered name is relative (or the apex '@'),
    matching the Cloudflare-style behavior of auto-qualifying against the zone.
    """
    if not name or not zone_name:
        return

    name = name.lower()
    zone_name = zone_name.lower()

    if name == "@":
        fqdn = zone_name
    elif name == zone_name or name.endswith(f".{zone_name}"):
        fqdn = name
    else:
        fqdn = f"{name}.{zone_name}"

    if len(fqdn) > DNS_NAME_MAX_LENGTH:
        raise ValidationError(DNS_NAME_LENGTH_ERROR_MESSAGE)


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
        raise ValidationError("Enter content using quotation marks at the beginning and end.")

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
        raise ValidationError(MX_CONTENT_SPACES_ERROR_MESSAGE)

    if len(content) > MX_CONTENT_MAX_LENGTH:
        raise ValidationError("Name must be no more than 253 characters.")


# Add this here temporarily, consider creating a cleaners.py file
def clean_txt_content(content: str) -> str:
    """Clean the content field for TXT records to ensure it is enclosed in quotes."""
    if content and not (content.startswith('"') and content.endswith('"')):
        return f'"{content}"'
    return content
