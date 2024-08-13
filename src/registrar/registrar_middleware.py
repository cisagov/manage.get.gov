"""
Contains middleware used in settings.py
"""

import logging
from urllib.parse import parse_qs
from django.urls import reverse
from django.http import HttpResponseRedirect
from registrar.models.user import User
from waffle.decorators import flag_is_active
from django.utils.deprecation import MiddlewareMixin

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

        self.excluded_pages = {
            self.setup_page: self.regular_excluded_pages,
            self.profile_page: self.other_excluded_pages,
        }

    def _get_excluded_pages(self, page):
        return self.excluded_pages.get(page, [])

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
            profile_page = self.profile_page
            if request.user.verification_type == User.VerificationTypeChoices.REGULAR:
                profile_page = self.setup_page
            if hasattr(request.user, "finished_setup") and not request.user.finished_setup:
                return self._handle_user_setup_not_finished(request, profile_page)

        # Continue processing the view
        return None

    def _handle_user_setup_not_finished(self, request, profile_page):
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
        if not any(request.path.startswith(page) for page in self._get_excluded_pages(profile_page)):

            # Preserve the original query parameters, and coerce them into a dict
            query_params = parse_qs(request.META["QUERY_STRING"])

            # Set the redirect value to our redirect location
            if custom_redirect is not None:
                query_params["redirect"] = custom_redirect

            # Add our new query param, while preserving old ones
            new_setup_page = replace_url_queryparams(profile_page, query_params) if query_params else profile_page

            return HttpResponseRedirect(new_setup_page)
        else:
            # Process the view as normal
            return None


class CheckPortfolioMiddleware:
    """
    Checks if the current user has a portfolio
    If they do, redirect them to the portfolio homepage when they navigate to home.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.home = reverse("home")

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        current_path = request.path

        if current_path == self.home and request.user.is_authenticated and request.user.is_org_user(request):

            if request.user.has_base_portfolio_permission():
                portfolio = request.user.portfolio

                # Add the portfolio to the request object
                request.portfolio = portfolio

                if request.user.has_domains_portfolio_permission():
                    portfolio_redirect = reverse("domains")
                else:
                    # View organization is the lowest access
                    portfolio_redirect = reverse("organization")

                return HttpResponseRedirect(portfolio_redirect)

        return None


class ANDIMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_template_view(self, request, view_func, view_args, view_kwargs):
        response = self.get_response(request)
        if "text/html" in response.get("Content-Type", ""):
            andi_script = """
            <script src="https://www.ssa.gov/accessibility/andi/andi.js"></script>
            """
            # Inject the ANDI script before the closing </body> tag
            content = response.content.decode("utf-8")
            content = content.replace("</body>", f"{andi_script}</body>")
            response.content = content.encode("utf-8")
        return None
