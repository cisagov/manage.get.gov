"""E2E regression tests: Organization Admin Experience (User 4).

User 4 setup (created by dev_auto_login persona=org_admin_4):
  Email:    regressiontest+4@gmail.com
  Role:     Organization admin
  Portfolio: 1 portfolio
  Permissions: Can manage portfolio members, view all domains/requests
  Assigned Domains: None (portfolio must have domains and domain requests)

Run:
  cd e2e
  pytest test_org_admin.py -v
  pytest test_org_admin.py -v --headed
  pytest test_org_admin.py -v --headed --slowmo 600
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


class TestOrgAdmin:
    """Regression tests for the Organization Admin experience (User 4)."""

    @staticmethod
    def _login(page, next_path="/"):
        dev_auto_login(page, "org_admin_4", next_path)

    def test_org_admin_home_page_display(self, video_page):
        """Org admin lands on the portfolio home with domains, requests, and Members link visible."""
        page = video_page
        self._login(page, next_path="/domains/")
        hide_debug_toolbar(page)

        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Expected portfolio home page."
        )

        assert_extended_header(page)
        assert page.locator(".organization-nav-link").is_visible(), (
            "Organization name should be visible in the navbar."
        )

        nav = page.get_by_label("Primary navigation")
        assert nav.get_by_role("link", name="Members", exact=True).is_visible(), (
            "Members link should be visible for org admin."
        )

        # Navigate to Domain Requests
        requests_link = nav.get_by_role("link", name="Domain requests", exact=True)
        requests_button = nav.get_by_role("button", name="Domain requests")
        if requests_button.is_visible():
            requests_button.click()
        else:
            requests_link.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        if not page.url.startswith(f"{BASE_URL}/requests/"):
            page.get_by_role("link", name="Domain requests").first.click()
            page.wait_for_load_state("networkidle")
            hide_debug_toolbar(page)

        wait_for_table_rows(page, "domain-requests__table-wrapper")
        assert page.locator("#domain-requests__table-wrapper tbody tr").count() > 0, (
            "Portfolio domain requests should be visible to org admin."
        )

        nav.get_by_role("link", name="Domains", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        wait_for_table_rows(page, "domains__table-wrapper")
        assert page.locator("#domains__table-wrapper tbody tr").count() > 0, (
            "Portfolio domains should be visible to org admin."
        )

    def test_org_admin_access_to_organization_page(self, video_page):
        """Org admin can load /organization/ successfully (not 403)."""
        page = video_page
        self._login(page, next_path="/domains/")
        hide_debug_toolbar(page)

        page.goto(f"{BASE_URL}/organization/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert page.url.startswith(f"{BASE_URL}/organization") or page.locator("h1").first.is_visible(), (
            "Organization overview page should load."
        )
        assert_extended_header(page)

    def test_org_admin_manage_members(self, video_page):
        """Org admin can reach the members page and sees the Add a new member button."""
        page = video_page
        self._login(page, next_path="/domains/")
        hide_debug_toolbar(page)

        nav = page.get_by_label("Primary navigation")
        nav.get_by_role("link", name="Members", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert page.url.startswith(f"{BASE_URL}/members") or page.locator("h1").first.is_visible(), (
            "Member management page should load."
        )
        assert_extended_header(page)

        try:
            page.wait_for_selector("#members__table-wrapper tbody tr", timeout=15_000)
            assert page.locator("#members__table-wrapper tbody tr").count() > 0, (
                "Member list should display."
            )
        except Exception:
            assert page.locator("table tbody tr").count() > 0, (
                "Member list should display."
            )

        add_member_button = page.locator("a", has_text="Add a new member").or_(
            page.locator("button", has_text="Add a new member")
        )
        assert add_member_button.is_visible(), (
            "Add a new member button should be visible for org admin."
        )
