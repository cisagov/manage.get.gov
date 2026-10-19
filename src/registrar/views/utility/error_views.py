"""
Custom views that allow for error view customization.

Used as a general handler for 500 errors both coming from the registrar app, but
also the djangooidc app.

If Djangooidc is left to its own devices and uses reverse directly,
then both context and session information will be obliterated due to:

a) Djangooidc being out of scope for context_processors
b) Potential cyclical import errors restricting what kind of data is passable.

Rather than dealing with that, we keep everything centralized in one location.
"""

from django.shortcuts import render
from registrar.logging_context import get_user_log_context


def custom_500_error_view(request, context=None):
    """Used to redirect 500 errors to a custom view"""
    context = dict(context or {})
    request_id = get_user_log_context().get("request_id")
    if request_id:
        context["log_identifier"] = request_id

    response = render(request, "500.html", context=context, status=500)
    # If page is using htmx, update the headers so the custom error view can be swapped
    if request.headers.get("HX-Request"):
        response["HX-Retarget"] = "body"
        response["HX-Reswap"] = "innerHTML"
    return response


def custom_401_error_view(request, context=None):
    """Used to redirect 401 errors to a custom view"""
    if context is None:
        context = {}
    return render(request, "401.html", context=context, status=401)


def custom_403_error_view(request, exception=None, context=None):
    """Used to redirect 403 errors to a custom view"""
    if context is None:
        context = {}
    return render(request, "403.html", context=context, status=403)


def custom_404_error_view(request, exception=None, context=None):
    """Used to redirect 404 errors to a custom view"""
    if context is None:
        context = {}
    return render(request, "404.html", context=context, status=404)
