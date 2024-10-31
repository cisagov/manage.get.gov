"""
Contains middleware used in settings.py
"""

import logging
from urllib.parse import parse_qs
from django.urls import reverse
from django.http import HttpResponseRedirect
from registrar.models import User
from waffle.decorators import flag_is_active
from django.urls import resolve, Resolver404
from registrar.config.urls import DOMAIN_REQUEST_NAMESPACE
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
            # These are here as there is a bug with this middleware that breaks djangos built in debug console.
            # The debug console uses this directory, but since this overrides that, it throws errors.
            "/__debug__",
        ]
        self.other_excluded_pages = [
            self.profile_page,
            self.logout_page,
            "/admin",
            "/__debug__",
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
    this middleware should serve two purposes:
      1 - set the portfolio in session if appropriate   # views will need the session portfolio
      2 - if path is home and session portfolio is set, redirect based on permissions of user
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.home = reverse("home")

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        current_path = request.path

        if not request.user.is_authenticated:
            return None

        # if multiple portfolios are allowed for this user
        if flag_is_active(request, "organization_feature"):
            self.set_portfolio_in_session(request)
        elif request.session.get("portfolio"):
            # Edge case: User disables flag while already logged in
            request.session["portfolio"] = None
        elif "portfolio" not in request.session:
            # Set the portfolio in the session if its not already in it
            request.session["portfolio"] = None

        if request.user.is_org_user(request):
            if current_path == self.home:
                if request.user.has_any_domains_portfolio_permission(request.session["portfolio"]):
                    portfolio_redirect = reverse("domains")
                else:
                    portfolio_redirect = reverse("no-portfolio-domains")
                return HttpResponseRedirect(portfolio_redirect)

        return None

    def set_portfolio_in_session(self, request):
        # NOTE: we will want to change later to have a workflow for selecting
        # portfolio and another for switching portfolio; for now, select first
        if flag_is_active(request, "multiple_portfolios"):
            request.session["portfolio"] = request.user.get_first_portfolio()
        else:
            request.session["portfolio"] = request.user.get_first_portfolio()


class NewRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None

        if request.session.get("new_request") is None:
            request.session["new_request"] = True

        resolved = resolve(request.path)
        if request.session.get("new_request") is False:
            try:
                resolved = resolve(request.path)
                # Check if we're in the domain-request namespace.
                # If not, then a new request is not being made.
                if resolved.namespace != DOMAIN_REQUEST_NAMESPACE:
                    request.session["new_request"] = True
            # URL doesn't match any known pattern.
            # This shouldn't happen (caught before this), but redundancy is good.
            except Resolver404:
                # If you somehow see this log, something must have went very, *very* wrong.
                # All I can offer in consolidation is this ASCII cat to tend to these hard times:
                # ⠀ ／l、
                # （ﾟ､ ｡ ７
                # ⠀ l、ﾞ ~ヽ
                #   じしf_, )ノ
                logger.error("[CRITICAL] NewRequestMiddleware => Could not resolve the request path.")

        return None
