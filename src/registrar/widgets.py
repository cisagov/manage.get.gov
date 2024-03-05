# widgets.py

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
