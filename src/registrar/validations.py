from django.core.validators import MaxLengthValidator

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

# Example (single-line text):
# forms.CharField(
#     validators=[get_max_length_validator(TEXT_EXTENDED)],
#     widget=forms.TextInput(attrs=get_max_length_attrs(TEXT_EXTENDED)),
# )

# Example (textarea):
# forms.CharField(
#     validators=[get_max_length_validator(TEXTAREA_LONG)],
#     widget=forms.Textarea(attrs=get_max_length_attrs(TEXTAREA_LONG)),
# )

# Example (email):
# forms.EmailField(
#     validators=[get_max_length_validator(EMAIL_MAX)],
#     widget=forms.EmailInput(attrs=get_max_length_attrs(EMAIL_MAX)),
# )

# Example (domain label like requested/alternative SLD):
# forms.CharField(
#     validators=[get_max_length_validator(DOMAIN_LABEL)],
#     widget=forms.TextInput(attrs=get_max_length_attrs(DOMAIN_LABEL)),
# )
"""

# Short single-line text inputs like first_name, last_name, city, urbanization, etc.
TEXT_SHORT = 100

# Extended single-line text inputs like address_line1/2, tribe_name, organization_name, titles, etc.
TEXT_EXTENDED = 255

# Multi-line textarea inputs like purpose, about, etc.
TEXTAREA_LONG = 2000

# Shorter textarea inputs like no_other_contacts_rationale
TEXTAREA_SHORT = 1000

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
