from django import template
from django.urls import reverse

from django.conf import settings

register = template.Library()


@register.simple_tag
def namespaced_url(namespace, name="", **kwargs):
    """Get a URL, given its Django namespace and name."""
    return reverse(f"{namespace}:{name}", kwargs=kwargs)


@register.filter("startswith")
def startswith(text, starts):
    if isinstance(text, str):
        return text.startswith(starts)
    return False


@register.filter("endswith")
def endswith(text, ends):
    if isinstance(text, str):
        return text.endswith(ends)
    return False


@register.filter("split")
def split_string(value, key):
    """
    Splits a given string
    """
    return value.split(key)


@register.simple_tag
def public_site_url(url_path):
    """Make a full URL for this path at our public site.

    The public site base url is set by a GETGOV_PUBLIC_SITE_URL environment
    variable.
    """
    base_url = settings.GETGOV_PUBLIC_SITE_URL
    # join the two halves with a single slash
    public_url = "/".join([base_url.rstrip("/"), url_path.lstrip("/")])
    return public_url
