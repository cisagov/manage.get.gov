"""
Contains middleware used in settings.py
"""

import logging
from urllib.parse import parse_qs
from django.urls import reverse
from django.http import HttpResponseRedirect
from registrar.models.portfolio import Portfolio
from registrar.models.user import User
from waffle.decorators import flag_is_active

from registrar.models.utility.generic_helper import replace_url_queryparams

logger = logging.getLogger(__name__)

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


class CheckUserProfileMiddleware:
    """
    Checks if the current user has finished_setup = False.
    If they do, redirect them to the setup page regardless of where they are in
    the application.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        self.setup_page = reverse("finish-user-profile-setup")
        self.profile_page = reverse("user-profile")
        self.logout_page = reverse("logout")
        self.regular_excluded_pages = [
            self.setup_page,
            self.logout_page,
            "/admin",
        ]
        self.other_excluded_pages = [
            self.profile_page,
            self.logout_page,
            "/admin",
        ]

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Runs pre-processing logic for each view. Checks for the
        finished_setup flag on the current user. If they haven't done so,
        then we redirect them to the finish setup page."""
        # Check that the user is "opted-in" to the profile feature flag
        has_profile_feature_flag = flag_is_active(request, "profile_feature")

        # If they aren't, skip this check entirely
        if not has_profile_feature_flag:
            return None

        if request.user.is_authenticated:
            if hasattr(request.user, "finished_setup") and not request.user.finished_setup:
                if request.user.verification_type == User.VerificationTypeChoices.REGULAR:
                    return self._handle_regular_user_setup_not_finished(request)
                else:
                    return self._handle_other_user_setup_not_finished(request)

        # Continue processing the view
        return None

    def _handle_regular_user_setup_not_finished(self, request):
        """Redirects the given user to the finish setup page.

        We set the "redirect" query param equal to where the user wants to go.

        If the user wants to go to '/request/', then we set that
        information in the query param.

        Otherwise, we assume they want to go to the home page.
        """

        # In some cases, we don't want to redirect to home. This handles that.
        # Can easily be generalized if need be, but for now lets keep this easy to read.
        custom_redirect = "domain-request:" if request.path == "/request/" else None

        # Don't redirect on excluded pages (such as the setup page itself)
        if not any(request.path.startswith(page) for page in self.regular_excluded_pages):

            # Preserve the original query parameters, and coerce them into a dict
            query_params = parse_qs(request.META["QUERY_STRING"])

            # Set the redirect value to our redirect location
            if custom_redirect is not None:
                query_params["redirect"] = custom_redirect

            # Add our new query param, while preserving old ones
            new_setup_page = replace_url_queryparams(self.setup_page, query_params) if query_params else self.setup_page

            return HttpResponseRedirect(new_setup_page)
        else:
            # Process the view as normal
            return None

    def _handle_other_user_setup_not_finished(self, request):
        """Redirects the given user to the profile page to finish setup."""

        # Don't redirect on excluded pages (such as the setup page itself)
        if not any(request.path.startswith(page) for page in self.other_excluded_pages):
            return HttpResponseRedirect(self.profile_page)
        else:
            # Process the view as normal
            return None
        
class CheckOrganizationMiddleware:
    """
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.home = reverse("home")
        self.json1 = reverse("get_domains_json")
        self.json2 = reverse("get_domain_requests_json")

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        current_path = request.path
        logger.debug(f"Current path: {current_path}")

        # Avoid infinite loop by skipping the redirect check on the home-organization URL and other JSON URLs
        if current_path in [self.json1, self.json2] or current_path.startswith('/admin'):
            logger.debug("Skipping middleware check for home-organization and JSON URLs")
            return None

        has_organization_feature_flag = flag_is_active(request, "organization_feature")
        logger.debug(f"Flag is active: {has_organization_feature_flag}")

        if has_organization_feature_flag:
            if request.user.is_authenticated:
                user_portfolios = Portfolio.objects.filter(creator=request.user)
                if user_portfolios.exists():
                    first_portfolio = user_portfolios.first()
                    home_organization_with_portfolio = reverse("home-organization", kwargs={'portfolio_id': first_portfolio.id})
                    
                    if current_path != home_organization_with_portfolio:
                        logger.debug(f"User has portfolios, redirecting to {home_organization_with_portfolio}")
                        return HttpResponseRedirect(home_organization_with_portfolio)
        return None
