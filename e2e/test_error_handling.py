"""E2E regression tests: Error Handling and Edge Cases.

Run:
  cd e2e
  pytest test_error_handling.py -v
  pytest test_error_handling.py -v --headed
  pytest test_error_handling.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import BASE_URL, assert_basic_header, assert_extended_header, hide_debug_toolbar

logger = logging.getLogger(__name__)


class TestErrorHandling:
    """Regression tests for error handling and edge cases."""

    @staticmethod
    def _login_legacy(page, next_path="/"):
        dev_auto_login(page, "legacy_user_1", next_path)

    @staticmethod
    def _login_basic(page, next_path="/domains/"):
        dev_auto_login(page, "portfolio_user_2", next_path)

    def test_legacy_user_blocked_from_portfolio_pages(self, video_page):
        """Legacy user is blocked from /organization/ with a 403 or redirect, and can navigate back."""
        page = video_page
        self._login_legacy(page, next_path="/")
        hide_debug_toolbar(page)

        assert_basic_header(page)

        page.goto(f"{BASE_URL}/organization/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        is_blocked = (
            page.locator("h2", has_text="403").is_visible()
            or page.locator("text=Access Denied").is_visible()
            or page.locator("text=Forbidden").is_visible()
            or page.locator("text=You do not have permission").is_visible()
            or not page.url.startswith(f"{BASE_URL}/organization")
        )
        assert is_blocked, (
            f"Legacy user should be blocked from /organization/. URL: {page.url}"
        )

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.locator("h1").first.is_visible(), (
            "User should be able to navigate back to home after being blocked."
        )

    def test_non_admin_sees_readonly_organization_page(self, video_page):
        """Basic portfolio member sees the org page read-only (no Edit buttons)."""
        page = video_page
        self._login_basic(page, next_path="/domains/")
        hide_debug_toolbar(page)

        page.goto(f"{BASE_URL}/organization/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert page.url.startswith(f"{BASE_URL}/organization") or page.locator("h1").first.is_visible(), (
            "Basic member should be able to view the organization page."
        )

        assert_extended_header(page)

        edit_button = page.locator("a.usa-button", has_text="Edit")
        assert not edit_button.is_visible(), (
            "Edit button should NOT be visible for basic members on the organization page."
        )

    def test_unauthenticated_access_redirects_to_login(self, video_page):
        """Unauthenticated access to protected pages redirects away from the target URL."""
        page = video_page

        page.goto(f"{BASE_URL}/domains/")
        page.wait_for_load_state("networkidle")
        assert not page.url.startswith(f"{BASE_URL}/domains/"), (
            "Unauthenticated user should not have access to /domains/."
        )

        page.goto(f"{BASE_URL}/members/")
        page.wait_for_load_state("networkidle")
        assert not page.url.startswith(f"{BASE_URL}/members/"), (
            "Unauthenticated user should not have access to /members/."
        )
