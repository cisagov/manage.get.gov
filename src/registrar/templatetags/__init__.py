"""Custom template tags to make our lives easier."""

from django.template.defaulttags import register


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
