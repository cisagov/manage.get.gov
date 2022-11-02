from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def radio_buttons_by_value(boundfield):
    """
    Returns radio button subwidgets indexed by their value.

    This makes it easier to visually identify the choices when
    using them in templates.
    """
    return {w.data["value"]: w for w in boundfield.subwidgets}


@register.simple_tag
def trigger(boundfield, *triggers):
    """
    Inserts HTML to link a dynamic question to its trigger(s).

    Currently only works for radio buttons.

    Also checks whether the question should be hidden on page load.
    If the question is already answered or if the question's
    trigger is already selected, it should not be hidden.

    Returns HTML attributes which will be read by a JavaScript
    helper, if the user has JavaScript enabled.
    """
    ids = []
    hide_on_load = True

    for choice in boundfield.subwidgets:
        if choice.data["selected"]:
            hide_on_load = False

    for trigger in triggers:
        ids.append(trigger.id_for_label)
        if trigger.data["selected"]:
            hide_on_load = False

    html = format_html(
        'toggle-by="{}"{}', ",".join(ids), " hide-on-load" if hide_on_load else ""
    )

    return html
