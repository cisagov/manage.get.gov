from django import template
import re
from registrar.models.domain_application import DomainApplication

register = template.Library()


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
def get_organization_long_name(organization_type):
    organization_choices_dict = {}

    for name, value in DomainApplication.OrganizationChoicesVerbose.choices:
        organization_choices_dict[name] = value

    long_form_type = organization_choices_dict[organization_type]
    if long_form_type is not None:
        return long_form_type

    return "Error"
