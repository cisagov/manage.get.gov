from django import template
import re

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
