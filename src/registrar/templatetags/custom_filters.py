import logging
from django import template
import re
from registrar.models.domain_request import DomainRequest

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


@register.filter(name='reverse_list')
def reverse_list(value):
    return reversed(value)

