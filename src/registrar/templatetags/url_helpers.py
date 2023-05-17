from urllib.parse import urljoin

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


@register.simple_tag
def public_site_url(url_path):
    """Make a full URL for this path at our public site.

    The public site base url is set by a GETGOV_PUBLIC_SITE_URL environment
    variable.
    """
    base_url = settings.GETGOV_PUBLIC_SITE_URL
    public_url = urljoin(base_url, url_path)
    return public_url
