from django.http import Http404


def always_404(_, reason=None):
    """Helpful view which always returns 404."""
    raise Http404(reason)
