"""E2E regression tests: Portfolio User Basic Experience (User 2).

User 2 setup (created by dev_auto_login persona=portfolio_user_2):
  Email:    regressiontest+2@gmail.com
  Role:     Basic member - domain manager
  Portfolio: 1 portfolio
  Permissions: Portfolio permissions only (no requester or admin privileges)
  Assigned Domains: At least 1 domain in portfolio

Run:
  cd e2e
  pytest test_portfolio_user_basic.py -v
  pytest test_portfolio_user_basic.py -v --headed
  pytest test_portfolio_user_basic.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import (
    BASE_URL,
    assert_extended_header,
    assert_portfolio_footer,
    hide_debug_toolbar,
    wait_for_table_rows,
)

logger = logging.getLogger(__name__)


class TestPortfolioUserBasic:
    """Regression tests for the basic portfolio user experience (User 2)."""

    @staticmethod
    def _login(page, next_path="/domains/"):
        dev_auto_login(page, "portfolio_user_2", next_path)

    @staticmethod
    def _assert_org_page_blocked(page):
        """Assert /your-organizations/ is blocked by 403 or redirects away."""
        if page.url.startswith(f"{BASE_URL}/your-organizations"):
            assert (
                page.locator("text=403").is_visible()
                or page.locator("text=Access Denied").is_visible()
                or page.locator("text=Forbidden").is_visible()
            ), "Organization page should be blocked with 403-type messaging."
        else:
            allowed = [f"{BASE_URL}/", f"{BASE_URL}/domains/"]
            assert any(page.url.startswith(r) for r in allowed), (
                f"Organization page access should redirect away. Got: {page.url}"
            )

    def test_portfolio_user_home_page_display_and_no_requests_access(self, video_page):
        """Portfolio home shows dual navbar, domains table, org name, and the correct footer."""
        page = video_page
        hide_debug_toolbar(page)
        self._login(page, next_path="/domains/")

        assert (
            page.locator("h1", has_text="Manage your domains").is_visible()
            or page.locator("h1", has_text="Domains").is_visible()
        ), "Expected a domains heading on the portfolio home page."

        wait_for_table_rows(page, "domains__table-wrapper")
        assert page.locator("#domains__table-wrapper").is_visible(), (
            "Domains table wrapper should be visible."
        )

        assert_extended_header(page)
        assert page.locator(".usa-nav__username").is_visible(), (
            "User email should appear in the top nav."
        )
        assert page.locator("div.usa-nav__secondary").is_visible(), (
            "Secondary navbar should be visible."
        )

        nav = page.get_by_label("Primary navigation")
        assert nav.get_by_role("link", name="Domains", exact=True).is_visible(), (
            "Domains tab should be visible."
        )
        assert nav.get_by_role("link", name="Domain requests", exact=True).is_visible(), (
            "Domain requests tab should be visible."
        )
        assert page.locator(".organization-nav-link").is_visible(), (
            "Organization name should appear in the secondary navbar."
        )

        assert_portfolio_footer(page)

        assert not page.locator("a", has_text="Manage members").is_visible(), (
            "Manage members should NOT be visible for basic members."
        )

        # Click Domain Requests tab — basic member has no requester permissions
        page.get_by_role("link", name="Domain requests", exact=True).first.click()
        page.wait_for_load_state("networkidle")

        if page.locator("text=Access Denied").is_visible() or page.locator("text=403").is_visible():
            pass  # expected — no requester permissions
        else:
            assert not page.locator("button", has_text="Create New Request").is_visible(), (
                "Create New Request should NOT be visible for non-requester users."
            )

    def test_portfolio_user_manage_domain(self, video_page):
        """Managing a domain shows the dual navbar, no Senior Official details, and the full footer."""
        page = video_page
        hide_debug_toolbar(page)
        self._login(page, next_path="/domains/")
        wait_for_table_rows(page, "domains__table-wrapper")

        page.locator("#domains__table-wrapper a", has_text="Manage").first.click()
        page.wait_for_load_state("networkidle")

        assert (
            page.locator("h1", has_text="Domain").is_visible()
            or page.locator("text=Domain").is_visible()
        ), "Domain management page should load."

        assert_extended_header(page)
        assert page.locator(".organization-nav-link").is_visible(), (
            "Organization name should remain in the navbar."
        )

        assert not page.locator("h3", has_text="Senior official").is_visible(), (
            "Senior official section should NOT be visible on portfolio domain pages."
        )

        suborg_field = page.locator("input[name='suborganization']")
        if suborg_field.is_visible():
            assert (
                suborg_field.get_attribute("readonly") is not None
                or suborg_field.get_attribute("disabled") is not None
            ), "Suborganization field should be read-only for basic members."

        assert_portfolio_footer(page)

    def test_portfolio_user_cannot_access_organization_page(self, video_page):
        """Navigating to /your-organizations/ is blocked; nav links still work afterward."""
        page = video_page
        hide_debug_toolbar(page)
        self._login(page, next_path="/domains/")

        response = page.goto(f"{BASE_URL}/your-organizations/")
        page.wait_for_load_state("networkidle")

        if response is not None and response.status == 302 and page.url.startswith(
            f"{BASE_URL}/openid/login/"
        ):
            pytest.fail("Auto-login did not create a valid portfolio session.")

        self._assert_org_page_blocked(page)
        assert_extended_header(page)

        domains_link = page.get_by_label("Primary navigation").get_by_role(
            "link", name="Domains", exact=True
        )
        domains_link.click()
        page.wait_for_load_state("networkidle")
        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Should be able to navigate back to the domains page."
        )

    def test_portfolio_user_profile_page(self, video_page):
        """Profile page shows the dual navbar and has email as readonly."""
        page = video_page
        hide_debug_toolbar(page)
        self._login(page, next_path="/domains/")

        page.locator(".usa-nav__username").click()
        page.get_by_label("Primary navigation").get_by_role(
            "link", name="Your profile"
        ).first.click()
        page.wait_for_load_state("networkidle")

        assert (
            page.locator("h1", has_text="Your profile").is_visible()
            or page.locator("text=Your profile").is_visible()
        ), "Profile editing page should load."

        assert_extended_header(page)
        assert page.locator(".organization-nav-link").is_visible(), (
            "Organization name should be visible in the navbar."
        )

        email_field = page.locator("input[name='email']")
        if email_field.is_visible():
            assert (
                email_field.get_attribute("readonly") is not None
                or email_field.get_attribute("disabled") is not None
            ), "Email field should be readonly or disabled."

        assert_portfolio_footer(page)
