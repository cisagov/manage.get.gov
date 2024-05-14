"""
Contains middleware used in settings.py
"""
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from django.urls import reverse, resolve
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


        # Check if setup is not finished
        finished_setup = hasattr(request.user, "finished_setup") and request.user.finished_setup
        if request.user.is_authenticated and not finished_setup:
            # redirect_to_domain_request = request.GET.get('domain_request', "") != ""
            setup_page = reverse(
                "finish-contact-profile-setup", 
                kwargs={"pk": request.user.contact.pk}
            )
            logout_page = reverse("logout")
            excluded_pages = [
                setup_page,
                logout_page,
            ]
            custom_redirect = None

            # In some cases, we don't want to redirect to home.
            # This handles that.
            if request.path == "/request/":
                # This can be generalized if need be, but for now lets keep this easy to read.
                custom_redirect = "domain-request:"

            # Don't redirect on excluded pages (such as the setup page itself)
            if not any(request.path.startswith(page) for page in excluded_pages):
                # Preserve the original query parameters, and coerce them into a dict
                query_params = parse_qs(request.META['QUERY_STRING'])

                if custom_redirect is not None:
                    # Set the redirect value to our redirect location
                    query_params["redirect"] = custom_redirect

                if query_params:
                    # Split the URL into parts
                    setup_page_parts = list(urlparse(setup_page))
                    # Modify the query param bit
                    setup_page_parts[4] = urlencode(query_params)
                    # Reassemble the URL
                    setup_page = urlunparse(setup_page_parts)
                

                # Redirect to the setup page
                return HttpResponseRedirect(setup_page)

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