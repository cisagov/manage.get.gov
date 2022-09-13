from django.conf import settings

def language_code(request):
    """Add LANGUAGE_CODE to the template context."""
    return {"LANGUAGE_CODE": settings.LANGUAGE_CODE}
