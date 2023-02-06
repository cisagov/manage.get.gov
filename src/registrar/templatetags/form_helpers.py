from django import template
from django.forms import BaseFormSet

register = template.Library()


@register.filter
def isformset(value):
    return isinstance(value, BaseFormSet)
