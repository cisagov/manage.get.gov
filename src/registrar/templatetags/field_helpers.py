"""Custom field helpers for our inputs."""

from django import template

register = template.Library()


@register.inclusion_tag("includes/input_with_errors.html")
def input_with_errors(field, add_class=None):
    """Make an input field along with error handling.

    field is a form field instance. add_class is a string of additional
    classes (space separated) to add to "usa-input" on the <input> field.
    """
    input_class = "usa-input"
    if add_class:
        input_class += " " + add_class
    return {"field": field, "input_class": input_class}
