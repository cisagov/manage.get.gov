"""Custom field helpers for our inputs."""

import re

from django import template

register = template.Library()


@register.inclusion_tag("includes/input_with_errors.html", takes_context=True)
def input_with_errors(context, field=None):  # noqa: C901
    """Make an input field along with error handling.

    Args:
        field: The field instance.

    In addition to the explicit `field` argument, this inclusion_tag takes the
    following "widget-tweak-esque" parameters from the surrounding context.

    Context args:
        add_class: append to input element's `class` attribute
        add_error_class: like `add_class` but only if field.errors is not empty
        add_required_class: like `add_class` but only if field is required
        add_label_class: append to input element's label's `class` attribute
        add_legend_class: append to input element's legend's `class` attribute
        add_group_class: append to input element's surrounding tag's `class` attribute
        attr_* - adds or replaces any single html attribute for the input
        add_error_attr_* - like `attr_*` but only if field.errors is not empty
        toggleable_input: shows a simple edit button, and adds display-none to the input field.

    Example usage:
        ```
        {% for form in forms.0 %}
            {% with add_class="usa-input--medium" %}
                {% with attr_required=True attr_disabled=False %}
                    {% input_with_errors form.street_address1 %}
                {% endwith %}
            {% endwith %}
        {% endfor }

    There are a few edge cases to keep in mind:
        - a "maxlength" attribute will cause the input to use USWDS Character counter
        - the field's `use_fieldset` controls whether the output is label/field or
            fieldset/legend/field
        - checkbox label styling is different (this is handled, don't worry about it)
    """
    context = context.flatten()
    context["field"] = field

    # get any attributes specified in the field's definition
    attrs = dict(field.field.widget.attrs)

    # these will be converted to CSS strings
    classes = []
    label_classes = []
    legend_classes = []
    group_classes = []

    # this will be converted to an attribute string
    described_by = []

    if "class" in attrs:
        classes.append(attrs.pop("class"))

    # parse context for field attributes and classes
    # ---
    # here we loop through all items in the context dictionary
    # (this is the context which was being used to render the
    #  outer template in which this {% input_with_errors %} appeared!)
    # and look for "magic" keys -- these are used to modify the
    # appearance and behavior of the final HTML
    for key, value in context.items():
        if key.startswith("attr_"):
            attr_name = re.sub("_", "-", key[5:])
            attrs[attr_name] = value
        elif key.startswith("add_error_attr_") and field.errors:
            attr_name = re.sub("_", "-", key[15:])
            attrs[attr_name] = value

        elif key == "add_class":
            classes.append(value)
        elif key == "add_required_class" and field.required:
            classes.append(value)
        elif key == "add_error_class" and field.errors:
            classes.append(value)

        elif key == "add_label_class":
            label_classes.append(value)
        elif key == "add_legend_class":
            legend_classes.append(value)

        elif key == "add_group_class":
            group_classes.append(value)

        elif key == "toggleable_input":
            # Hide the primary input field.
            # Used such that we can toggle it with JS
            if "display-none" not in classes:
                classes.append("display-none")

    attrs["id"] = field.auto_id

    # do some work for various edge cases

    if "maxlength" in attrs:
        # associate the field programmatically with its hint text
        described_by.append(f"{attrs['id']}__message")

    if field.use_fieldset:
        context["label_tag"] = "legend"
    else:
        context["label_tag"] = "label"

    if field.use_fieldset:
        label_classes.append("usa-legend")

    if field.widget_type == "checkbox":
        label_classes.append("usa-checkbox__label")
    elif not field.use_fieldset:
        label_classes.append("usa-label")

    if field.errors:
        # associate the field programmatically with its error message
        message_div_id = f"{attrs['id']}__error-message"
        described_by.append(message_div_id)

        # set the field invalid
        # due to weirdness, this must be a string, not a boolean
        attrs["aria-invalid"] = "true"

        # style the invalid field
        classes.append("usa-input--error")
        label_classes.append("usa-label--error")
        group_classes.append("usa-form-group--error")

    # convert lists into strings

    if classes:
        context["classes"] = " ".join(classes)

    if label_classes:
        context["label_classes"] = " ".join(label_classes)

    if legend_classes:
        context["legend_classes"] = " ".join(legend_classes)

    if group_classes:
        context["group_classes"] = " ".join(group_classes)

    if described_by:
        # ensure we don't overwrite existing attribute value
        if "aria-describedby" in attrs:
            described_by.append(attrs["aria-describedby"])
        attrs["aria-describedby"] = " ".join(described_by)

    # ask Django to give us the widget dict
    # see Widget.get_context() on
    # https://docs.djangoproject.com/en/4.1/ref/forms/widgets
    widget = field.field.widget.get_context(
        field.html_name, field.value(), field.build_widget_attrs(attrs)
    )  # -> {"widget": {"name": ...}}

    context["widget"] = widget["widget"]

    return context
