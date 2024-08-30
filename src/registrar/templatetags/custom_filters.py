import logging
from django import template
import re
from registrar.models.domain_request import DomainRequest
from phonenumber_field.phonenumber import PhoneNumber

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter(name="extract_value")
def extract_value(html_input):
    match = re.search(r'value="([^"]*)"', html_input)
    if match:
        return match.group(1)
    return ""


@register.filter
def extract_a_text(value):
    # Use regex to extract the text within the <a> tag
    pattern = r"<a\b[^>]*>(.*?)</a>"
    match = re.search(pattern, value)
    if match:
        extracted_text = match.group(1)
    else:
        extracted_text = ""

    return extracted_text


@register.filter
def find_index(haystack, needle):
    try:
        return haystack.index(needle)
    except ValueError:
        return -1


@register.filter
def slice_after(value, substring):
    index = value.find(substring)
    if index != -1:
        result = value[index + len(substring) :]
        return result
    return value


@register.filter
def contains_checkbox(html_list):
    for html_string in html_list:
        if re.search(r'<input[^>]*type="checkbox"', html_string):
            return True
    return False


@register.filter
def get_organization_long_name(generic_org_type):
    organization_choices_dict = dict(DomainRequest.OrganizationChoicesVerbose.choices)
    long_form_type = organization_choices_dict[generic_org_type]
    if long_form_type is None:
        logger.error("Organization type error, triggered by a template's custom filter")
        return "Error"

    return long_form_type


@register.filter(name="has_permission")
def has_permission(user, permission):
    return user.has_perm(permission)


@register.filter
def get_region(state):
    if state and isinstance(state, str):
        regions = {
            "CT": 1,
            "ME": 1,
            "MA": 1,
            "NH": 1,
            "RI": 1,
            "VT": 1,
            "NJ": 2,
            "NY": 2,
            "PR": 2,
            "VI": 2,
            "DE": 3,
            "DC": 3,
            "MD": 3,
            "PA": 3,
            "VA": 3,
            "WV": 3,
            "AL": 4,
            "FL": 4,
            "GA": 4,
            "KY": 4,
            "MS": 4,
            "NC": 4,
            "SC": 4,
            "TN": 4,
            "IL": 5,
            "IN": 5,
            "MI": 5,
            "MN": 5,
            "OH": 5,
            "WI": 5,
            "AR": 6,
            "LA": 6,
            "NM": 6,
            "OK": 6,
            "TX": 6,
            "IA": 7,
            "KS": 7,
            "MO": 7,
            "NE": 7,
            "CO": 8,
            "MT": 8,
            "ND": 8,
            "SD": 8,
            "UT": 8,
            "WY": 8,
            "AZ": 9,
            "CA": 9,
            "HI": 9,
            "NV": 9,
            "GU": 9,
            "AS": 9,
            "MP": 9,
            "AK": 10,
            "ID": 10,
            "OR": 10,
            "WA": 10,
        }
        return regions.get(state.upper(), "N/A")
    else:
        return None


@register.filter
def format_phone(value):
    """Converts a phonenumber to a national format"""
    if value:
        phone_number = value
        if isinstance(value, str):
            phone_number = PhoneNumber.from_string(value)
        return phone_number.as_national
    return value


@register.filter
def in_path(url, path):
    return url in path


@register.filter(name="and")
def and_filter(value, arg):
    """
    Implements logical AND operation in templates.
    Usage: {{ value|and:arg }}
    """
    return bool(value and arg)


@register.filter(name="has_contact_info")
def has_contact_info(user):
    """Checks if the given object has the attributes: title, email, phone
    and checks if at least one of those is not null."""
    if not hasattr(user, "title") or not hasattr(user, "email") or not hasattr(user, "phone"):
        return False
    else:
        return bool(user.title or user.email or user.phone)


@register.filter
def model_name_lowercase(instance):
    return instance.__class__.__name__.lower()
