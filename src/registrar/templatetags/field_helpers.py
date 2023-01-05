"""Custom field helpers for our inputs."""

from django import template

register = template.Library()


def _field_context(field, input_class, add_class, required=False):
    if add_class:
        input_class += " " + add_class
    context = {"field": field, "input_class": input_class}
    if required:
        context["required"] = True
    return context


@register.inclusion_tag("includes/input_with_errors.html")
def input_with_errors(field, add_class=None):
    """Make an input field along with error handling.

    field is a form field instance. add_class is a string of additional
    classes (space separated) to add to "usa-input" on the <input> field.
    """
    return _field_context(field, "usa-input", add_class)


@register.inclusion_tag("includes/input_with_errors.html")
def select_with_errors(field, add_class=None, required=False):
    """Make a select field along with error handling.

    field is a form field instance. add_class is a string of additional
    classes (space separated) to add to "usa-select" on the field.
    """
    return _field_context(field, "usa-select", add_class, required)
