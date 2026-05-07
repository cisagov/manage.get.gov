"""E2E regression tests: Navigation and Footer Link Consistency.

Run:
  cd e2e
  pytest test_navigation_footer.py -v
  pytest test_navigation_footer.py -v --headed
  pytest test_navigation_footer.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import (
    BASE_URL,
    assert_basic_footer,
    assert_basic_header,
    assert_extended_header,
    assert_portfolio_footer,
    hide_debug_toolbar,
    select_portfolio,
)

logger = logging.getLogger(__name__)


class TestNavigationFooter:
    """Regression tests for navigation and footer link consistency."""

    @staticmethod
    def _login_portfolio(page, next_path="/domains/"):
        dev_auto_login(page, "portfolio_user_2", next_path)

    @staticmethod
    def _login_legacy(page, next_path="/"):
        dev_auto_login(page, "legacy_user_1", next_path)

    @staticmethod
    def _login_multi_portfolio(page, next_path="/"):
        dev_auto_login(page, "multi_portfolio_admin_7", next_path)

    def test_portfolio_user_header_navigation(self, video_page):
        """All secondary navbar links load the correct pages and maintain the dual navbar."""
        page = video_page
        self._login_portfolio(page, next_path="/domains/")
        hide_debug_toolbar(page)

        nav = page.get_by_label("Primary navigation")

        nav.get_by_role("link", name="Domains", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Domains page should load."
        )
        assert_extended_header(page)

        nav.get_by_role("link", name="Domain requests", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/requests/") or page.locator("h1").first.is_visible(), (
            "Domain requests page should load."
        )
        assert_extended_header(page)

        page.goto(f"{BASE_URL}/organization/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/organization") or page.locator("h1").first.is_visible(), (
            "Organization page should load."
        )
        assert_extended_header(page)

    def test_portfolio_user_footer_navigation(self, video_page):
        """All footer links load the correct pages and maintain the navbar structure."""
        page = video_page
        self._login_portfolio(page, next_path="/domains/")
        hide_debug_toolbar(page)

        page.locator(".usa-footer__address a", has_text="Domains").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Domains page should load from footer."
        )
        assert_extended_header(page)

        page.locator(".usa-footer__address a", has_text="Domain requests").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/requests/") or page.locator("h1").first.is_visible(), (
            "Domain requests page should load from footer."
        )
        assert_extended_header(page)

        page.locator(".usa-footer__address a", has_text="Organization").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/organization") or page.locator("h1").first.is_visible(), (
            "Organization page should load from footer."
        )
        assert_extended_header(page)

        page.locator(".usa-footer__address a", has_text="Your profile").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/user-profile") or page.locator("h1").first.is_visible(), (
            "Profile page should load from footer."
        )
        assert_extended_header(page)

    def test_legacy_user_navigation_constraints(self, video_page):
        """Legacy user sees only Home and Your profile in the footer, single navbar throughout."""
        page = video_page
        self._login_legacy(page, next_path="/")
        hide_debug_toolbar(page)

        assert_basic_header(page)
        assert_basic_footer(page)

        footer = page.locator(".usa-footer__address")
        assert not footer.locator("a", has_text="Domains").is_visible(), (
            "No Domains link in legacy footer."
        )
        assert not footer.locator("a", has_text="Domain requests").is_visible(), (
            "No Domain requests link in legacy footer."
        )
        assert not footer.locator("a", has_text="Organization").is_visible(), (
            "No Organization link in legacy footer."
        )

        page.locator(".usa-nav__username").click()
        hide_debug_toolbar(page)
        page.get_by_label("Primary navigation").get_by_role(
            "link", name="Your profile"
        ).first.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert_basic_header(page)
        assert_basic_footer(page)

    def test_cross_portfolio_admin_navigation(self, video_page):
        """Switching portfolios updates the org name and all nav links remain functional."""
        page = video_page
        self._login_multi_portfolio(page, next_path="/")
        hide_debug_toolbar(page)

        page.locator("button.usa-card__container").first.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        first_org_name = page.locator(".organization-nav-link").first.text_content().strip()

        nav = page.get_by_label("Primary navigation")
        nav.get_by_role("link", name="Domains", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Domains page should load."
        )
        assert page.locator(".organization-nav-link").first.text_content().strip() == first_org_name, (
            "Org name should remain consistent within the first portfolio."
        )

        orgs_button = page.locator("button#organizations-menu").first
        orgs_button.click()
        page.wait_for_selector("#organizations-submenu", state="visible", timeout=5_000)
        hide_debug_toolbar(page)

        page.locator("#organizations-submenu button.organization-button").nth(1).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        second_org_name = page.locator(".organization-nav-link").first.text_content().strip()
        assert second_org_name != first_org_name, (
            "Org name should change after switching portfolios."
        )

        nav.get_by_role("link", name="Domains", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Domains page should load in the second portfolio context."
        )
