"""E2E regression tests: Session Portfolio Management.

Run:
  cd e2e
  pytest test_session_management.py -v
  pytest test_session_management.py -v --headed
  pytest test_session_management.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import BASE_URL, assert_extended_header, hide_debug_toolbar, select_portfolio

logger = logging.getLogger(__name__)


class TestSessionManagement:
    """Regression tests for session portfolio management."""

    @staticmethod
    def _login_requester(page, next_path="/domains/"):
        dev_auto_login(page, "portfolio_user_requester_3", next_path)

    @staticmethod
    def _login_multi_portfolio(page, next_path="/"):
        dev_auto_login(page, "multi_portfolio_admin_7", next_path)

    def test_session_portfolio_persistence(self, video_page):
        """Portfolio context (org name) persists across Domains, Requests, and Profile pages."""
        page = video_page
        self._login_requester(page, next_path="/domains/")
        hide_debug_toolbar(page)

        nav = page.get_by_label("Primary navigation")
        first_org = page.locator(".organization-nav-link").first.text_content().strip()
        assert first_org != "", "Organization name should be present on login."

        nav.get_by_role("link", name="Domains", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert_extended_header(page)
        assert page.locator(".organization-nav-link").first.text_content().strip() == first_org, (
            "Org name should persist on the Domains page."
        )
        assert not page.locator("text=Select a portfolio").is_visible(), (
            "No unexpected redirect to the portfolio selector."
        )

        btn = nav.get_by_role("button", name="Domain requests")
        if btn.is_visible():
            btn.click()
            page.locator("#basic-nav-section-two a").first.click()
        else:
            nav.get_by_role("link", name="Domain requests", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert_extended_header(page)
        assert page.locator(".organization-nav-link").first.text_content().strip() == first_org, (
            "Org name should persist on the Domain requests page."
        )

        page.locator("button#user-profile-menu").first.click()
        page.locator("#user-profile-submenu a", has_text="Your profile").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert_extended_header(page)
        assert page.locator(".organization-nav-link").first.text_content().strip() == first_org, (
            "Org name should persist on the Profile page."
        )

    def test_portfolio_selection_session_update(self, video_page):
        """Switching from Portfolio A to Portfolio B updates the session and all subsequent pages."""
        page = video_page
        self._login_multi_portfolio(page, next_path="/")
        hide_debug_toolbar(page)

        select_portfolio(page, index=0)
        org_name_a = page.locator(".organization-nav-link").first.text_content().strip()
        assert org_name_a != "", "Org name A should be visible."

        nav = page.get_by_label("Primary navigation")
        nav.get_by_role("link", name="Domains", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.locator(".organization-nav-link").first.text_content().strip() == org_name_a, (
            "Session should maintain Portfolio A context."
        )

        orgs_button = page.locator("button#organizations-menu").first
        orgs_button.click()
        page.wait_for_selector("#organizations-submenu", state="visible", timeout=5_000)
        hide_debug_toolbar(page)

        page.locator("#organizations-submenu button.organization-button").nth(1).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        org_name_b = page.locator(".organization-nav-link").first.text_content().strip()
        assert org_name_b != org_name_a, (
            f"Session should update to Portfolio B. Got '{org_name_b}' vs '{org_name_a}'"
        )

        nav.get_by_role("button", name="Domain requests").click()
        page.locator("#basic-nav-section-two a").first.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert page.locator(".organization-nav-link").first.text_content().strip() == org_name_b, (
            "Domain requests page should use Portfolio B context."
        )
        assert page.locator(".organization-nav-link").first.text_content().strip() != org_name_a, (
            "No stale Portfolio A data should display."
        )
