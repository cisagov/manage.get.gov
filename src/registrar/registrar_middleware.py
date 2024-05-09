"""
Contains middleware used in settings.py
"""

from django.urls import reverse
from django.http import HttpResponseRedirect

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
        # Check if the user is authenticated and if the setup is not finished
        if request.user.is_authenticated and not request.user.finished_setup:
            # Redirect to the setup page
            return HttpResponseRedirect(reverse('finish-contact-profile-setup'))

        # Continue processing the view
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