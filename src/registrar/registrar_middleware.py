"""
Contains middleware used in settings.py
"""

import logging
import time
import re
from urllib.parse import parse_qs
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.urls import resolve
from django.db import connections
from registrar.models import User
from waffle.decorators import flag_is_active

from registrar.models.utility.generic_helper import replace_url_queryparams
from .logging_context import set_user_log_context

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

        If the user wants to go to '/request/start/' or '/request/', then we set that
        information in the query param.

        Otherwise, we assume they want to go to the home page.
        """

        # In some cases, we don't want to redirect to home. This handles that.
        # Can easily be generalized if need be, but for now lets keep this easy to read.
        start_paths = ["/request/", "/request/start/"]
        custom_redirect = "domain-request:start" if request.path in start_paths else None

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
        self.legacy_home = "legacy_home"

        self.select_portfolios_page = reverse("your-organizations")
        self.set_portfolio_page = reverse("set-session-portfolio")
        self.setup_page = reverse("finish-user-profile-setup")
        self.profile_page = reverse("user-profile")
        self.logout_page = reverse("logout")

        self.excluded_pages = [
            self.setup_page,
            self.logout_page,
            self.profile_page,
            self.select_portfolios_page,
            self.set_portfolio_page,
            "/admin",
            # These are here as there is a bug with this middleware that breaks djangos built in debug console.
            # The debug console uses this directory, but since this overrides that, it throws errors.
            "/__debug__",
        ]

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def _is_excluded(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.excluded_pages)

    def _is_data_api(self, request):
        return request.path in {
            reverse("get_domains_json"),
            reverse("get_domain_requests_json"),
        }

    def _wants_html(self, request):
        accept = request.META.get("HTTP_ACCEPT")
        return (not accept) or ("text/html" in accept) or ("*/*" in accept)

    def _set_or_clear_portfolio(self, request):
        """Ensure session['portfolio'] is consistent with user/org state."""

        # On legacy clicks clear portfolio & stop
        if request.GET.get(self.legacy_home) == "1":
            request.session.pop("portfolio", None)
            return

        user = request.user
        multiple = flag_is_active(request, "multiple_portfolios")
        first_portfolio = user.get_first_portfolio()

        # Set if feature off and user has any portfolio OR user has exactly one portfolio
        if (not multiple and first_portfolio) or (user.get_num_portfolios() == 1 and not user.has_legacy_domain()):
            request.session["portfolio"] = first_portfolio
            return

        # Clear if session portfolio is not valid anymore
        if request.session.get("portfolio") and not user.is_org_user(request):
            request.session.pop("portfolio", None)

    def _maybe_redirect_to_org_select(self, request):
        """If user has multiple orgs and no active portfolio (and not on excluded paths), send to select page."""
        if request.GET.get(self.legacy_home) == "1":
            return None
        # Never redirect explicit legacy clicks; never redirect JSON/APIs etc. only HTML views
        if self._is_excluded(request.path) or self._is_data_api(request) or not self._wants_html(request):
            return None
        if request.user.is_multiple_orgs_user(request) and not request.session.get("portfolio"):
            return HttpResponseRedirect(self.select_portfolios_page)
        return None

    def _home_redirect(self, request):
        """Handle all home page redirections."""
        if request.GET.get(self.legacy_home) == "1":
            return None
        if request.path != self.home:
            return None

        user = request.user
        multiple = user.is_multiple_orgs_user(request)
        any_org = user.is_any_org_user()

        # If multi-org OR legacy+any_org, go to org select
        if multiple or (user.has_legacy_domain() and any_org):
            return HttpResponseRedirect(self.select_portfolios_page)

        # If portfolio is present, choose domains vs no-portfolio-domains
        portfolio = request.session.get("portfolio")
        has_portfolio_domains = (flag_is_active(request, "multiple_portfolios") and any_org) or user.is_org_user(
            request
        )

        if has_portfolio_domains and portfolio:
            target = (
                reverse("domains")
                if user.has_any_domains_portfolio_permission(portfolio)
                else reverse("no-portfolio-domains")
            )
            return HttpResponseRedirect(target)

        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None

        # Legacy-home click
        # If user clicked "legacy home", clear portfolio
        if request.path == self.home and request.GET.get(self.legacy_home) == "1":
            request.session.pop("portfolio", None)
            return None

        # Keep session['portfolio'] in sync on normal HTML page views
        # (Skip admin/debug/data APIs; only do this for HTML page loads)
        if not self._is_excluded(request.path) and not self._is_data_api(request):
            self._set_or_clear_portfolio(request)

        # Maybe send multi-org users to org-select page
        resp = self._maybe_redirect_to_org_select(request)
        if resp:
            return resp

        # Home redirect logic (domains vs no-portfolio-domains)
        resp = self._home_redirect(request)
        if resp:
            return resp

        return None


class RestrictAccessMiddleware:
    """
    Middleware that blocks access to all views unless explicitly permitted.

    This middleware enforces authentication by default. Views must explicitly allow access
    using access control mechanisms such as the `@grant_access` decorator. Exceptions are made
    for Django admin views, explicitly ignored paths, and views that opt out of login requirements.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Compile regex patterns from settings to identify paths that bypass login requirements
        self.ignored_paths = [re.compile(pattern) for pattern in getattr(settings, "LOGIN_REQUIRED_IGNORE_PATHS", [])]

    def __call__(self, request):

        # Allow requests to Django Debug Toolbar
        if request.path.startswith("/__debug__/"):
            return self.get_response(request)

        # Allow requests matching configured ignored paths
        if any(pattern.match(request.path) for pattern in self.ignored_paths):
            return self.get_response(request)

        # Attempt to resolve the request path to a view function
        try:
            resolver_match = resolve(request.path_info)
            view_func = resolver_match.func
            app_name = resolver_match.app_name  # Get the app name of the resolved view
        except Exception:
            # If resolution fails, allow the request to proceed (avoid blocking non-view routes)
            return self.get_response(request)

        # Automatically allow access to Django's built-in admin views (excluding custom /admin/* views)
        if app_name == "admin":
            return self.get_response(request)

        # Allow access if the view explicitly opts out of login requirements
        if getattr(view_func, "login_required", True) is False:
            return self.get_response(request)

        # Restrict access to views that do not explicitly declare access rules
        if not getattr(view_func, "has_explicit_access", False):
            raise PermissionDenied  # Deny access if the view lacks explicit permission handling

        return self.get_response(request)


class RequestLoggingMiddleware:
    """
    Middleware to log user email, remote address, and request path to prepend to logs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only log in production (stable)
        if getattr(settings, "IS_PRODUCTION", False):
            # Get user email (if authenticated), else None
            user_email = request.user.email if request.user.is_authenticated else None
            # Get remote IP address or IPv6 address
            forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if forwarded_for:
                remote_ip = forwarded_for.split(",")[0].strip()
            else:
                remote_ip = request.META.get("REMOTE_ADDR")
            # Get request path
            request_path = request.path

            # set user log info
            set_user_log_context(user_email, remote_ip, request_path)
            # Log user information
            logger.info("Router log")
        return self.get_response(request)


class DatabaseConnectionMiddleware:
    """
    Middleware to track database connection metrics and query performance.
    Uses the same callable pattern as RequestLoggingMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request._db_start_time = time.time()
        request._db_queries_start = len(connections["default"].queries)

        # Log connection state
        connection = connections["default"]
        logger.info(f"DB_CONN_START: queries_executed={len(connection.queries)}")
        response = self.get_response(request)
        if hasattr(request, "_db_start_time"):
            connection = connections["default"]
            query_count = len(connection.queries) - request._db_queries_start
            duration = time.time() - request._db_start_time

            # Get request ID for correlation
            request_id = request.META.get("HTTP_X_REQUEST_ID", "unknown")
            logger.info(
                f"DB_CONN_END: req_id={request_id}, "
                f"queries={query_count}, "
                f"duration={duration:.3f}s, "
                f"total_queries={len(connection.queries)}, "
                f"status={response.status_code}, "
                f"path={request.path}"
            )
        return response
