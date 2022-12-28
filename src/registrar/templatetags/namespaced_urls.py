from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag
def namespaced_url(namespace, name="", **kwargs):
    """Get a URL, given its Django namespace and name."""
    return reverse(f"{namespace}:{name}", kwargs=kwargs)
