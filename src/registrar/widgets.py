# widgets.py

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.safestring import mark_safe


class NoAutocompleteFilteredSelectMultiple(FilteredSelectMultiple):
    """Firefox and Edge are unable to correctly initialize the source select in filter_horizontal
    widgets. We add the attribute autocomplete=off to fix that."""

    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        attrs["autocomplete"] = "off"
        output = super().render(name, value, attrs=attrs, renderer=renderer)
        return mark_safe(output)  # nosec


class AdminTribeSelect(forms.Select):
    """One combined selector for fed and state tribes."""

    template_name = "django/admin/widgets/tribe_select_admin.html"

    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs, choices)
        self.related_widgets = {}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["related_widgets"] = []
        # Render a hidden dropdown for each tribe (Federal / State) model to use Django's pencil/view controls.
        # tribe-select-admin.js keeps the hidden dropdowns in sync with the user selected combined dropdown.
        for tribe_type, related_widget in self.related_widgets.items():
            choices, selected_pk = self._get_related_choices(context["widget"]["optgroups"], tribe_type)
            related_widget.choices = choices
            related_name = f"{name}_{tribe_type}"
            rendered_widget = related_widget.render(related_name, selected_pk, attrs={"id": f"id_{related_name}"})
            context["related_widgets"].append(
                {
                    "tribe_type": tribe_type,
                    "selected": selected_pk is not None,
                    "html": rendered_widget,
                }
            )
        return context

    def _get_related_choices(self, optgroups, tribe_type):
        """Return all choices for one hidden dropdown and its currently selected record ID.

        The visible selector combines federal and state records using values such as
        "federal:12" and "state:34". We have corresponding single-model hidden Django dropdowns
        for State and Federal that allow the Django eye/pencil to work (they expect single model
        dropdowns).

        So here we build either all the federal or all the state options, keeping every choice of
        that type, not just the selected one.  When an analyst changes the selection in the combined
        dropdown, updateRelatedTribeWidgets() in tribe-select-admin.js selects the matching existing
        option here to update the pencil/view links.

        We must have all options so if the analyst changes their selection, the hidden dropdowns can
        be updated to support the pencil/eye.
        """
        choices = [("", "---------")]
        selected_pk = None
        for _group_label, options, _group_index in optgroups:
            for option in options:
                if not option["value"]:
                    continue
                option_type, pk = str(option["value"]).split(":", 1)
                if option_type == tribe_type:
                    choices.append((pk, option["label"]))
                    if option["selected"]:
                        selected_pk = pk
        return choices, selected_pk
