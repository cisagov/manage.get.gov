"""
Contains middleware used in settings.py
"""

from urllib.parse import parse_qs
from django.urls import reverse
from django.http import HttpResponseRedirect
from waffle.decorators import flag_is_active

from registrar.models.utility.generic_helper import replace_url_queryparams


class CheckUserProfileMiddleware:
    """
    Checks if the current user has finished_setup = False.
    If they do, redirect them to the setup page regardless of where they are in
    the application.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """Code that gets executed on each request before the view is called"""
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):

        # Check that the user is "opted-in" to the profile feature flag
        has_profile_feature_flag = flag_is_active(request, "profile_feature")

        # If they aren't, skip this check entirely
        if not has_profile_feature_flag:
            return None

        # Check if setup is not finished
        finished_setup = hasattr(request.user, "finished_setup") and request.user.finished_setup
        if hasattr(request.user, "finished_setup"):
            user_values = [
                request.user.contact.first_name,
                request.user.contact.last_name,
                request.user.contact.title,
                request.user.contact.phone,
            ]
            if None in user_values:
                finished_setup = False

        if request.user.is_authenticated and not finished_setup:
            return self._handle_setup_not_finished(request)

        # Continue processing the view
        return None

    def _handle_setup_not_finished(self, request):
        setup_page = reverse("finish-user-profile-setup", kwargs={"pk": request.user.contact.pk})
        logout_page = reverse("logout")
        excluded_pages = [
            setup_page,
            logout_page,
        ]

        # In some cases, we don't want to redirect to home. This handles that.
        # Can easily be generalized if need be, but for now lets keep this easy to read.
        custom_redirect = "domain-request:" if request.path == "/request/" else None

        # Don't redirect on excluded pages (such as the setup page itself)
        if not any(request.path.startswith(page) for page in excluded_pages):
            # Preserve the original query parameters, and coerce them into a dict
            query_params = parse_qs(request.META["QUERY_STRING"])

            if custom_redirect is not None:
                # Set the redirect value to our redirect location
                query_params["redirect"] = custom_redirect

            if query_params:
                setup_page = replace_url_queryparams(setup_page, query_params)

            # Redirect to the setup page
            return HttpResponseRedirect(setup_page)
        else:
            # Process the view as normal
            return None


class NoCacheMiddleware:
    """
    Middleware to add Cache-control: no-cache to every response.

    Used to force Cloudfront caching to leave us alone while we develop
    better caching responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Cache-Control"] = "no-cache"
        return response
