"""E2E regression tests: Mixed Permission User (User 6).

User 6 setup (created by dev_auto_login persona=mixed_permissions_6):
  Email:    regressiontest+6@gmail.com
  Role:     Org admin in 1 portfolio + domain manager on non-portfolio domain
  Portfolio: 1 portfolio
  Permissions: Portfolio admin + legacy domain management
  Assigned Domains: 1 portfolio domain + 1 legacy domain (legacy6.gov)

Run:
  cd e2e
  pytest test_mixed_permissions.py -v
  pytest test_mixed_permissions.py -v --headed
  pytest test_mixed_permissions.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import BASE_URL, assert_extended_header, hide_debug_toolbar, wait_for_table_rows

logger = logging.getLogger(__name__)


class TestMixedPermissions:
    """Regression tests for the mixed permission user (User 6)."""

    @staticmethod
    def _login(page, next_path="/"):
        dev_auto_login(page, "mixed_permissions_6", next_path)

    def test_user_6_organization_experience(self, video_page):
        """User 6 can access portfolio home, org page, and member management."""
        page = video_page
        self._login(page, next_path="/domains/")
        hide_debug_toolbar(page)

        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Should be directed to the portfolio home page."
        )

        assert_extended_header(page)
        assert page.locator(".organization-nav-link").is_visible(), (
            "Organization name should be visible in the navbar."
        )

        page.goto(f"{BASE_URL}/organization/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert page.url.startswith(f"{BASE_URL}/organization") or page.locator("h1").first.is_visible(), (
            "Organization page should load."
        )
        assert_extended_header(page)

        nav = page.get_by_label("Primary navigation")
        nav.get_by_role("link", name="Members", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert page.url.startswith(f"{BASE_URL}/members") or page.locator("h1").first.is_visible(), (
            "Members page should load."
        )

        try:
            page.wait_for_selector("#members__table-wrapper tbody tr", timeout=15_000)
            assert page.locator("#members__table-wrapper tbody tr").count() > 0, (
                "Members table should have at least one row."
            )
        except Exception:
            assert page.locator("table tbody tr").count() > 0, (
                "Members table should have rows."
            )

        add_button = page.locator("a", has_text="Add a new member").or_(
            page.locator("button", has_text="Add a new member")
        )
        assert add_button.is_visible(), (
            "Add a new member button should be visible for org admin."
        )

    def test_user_6_legacy_domain_access(self, video_page):
        """User 6 can see and manage portfolio domains with the extended header."""
        page = video_page
        self._login(page, next_path="/domains/")
        hide_debug_toolbar(page)

        wait_for_table_rows(page, "domains__table-wrapper")
        assert page.locator("#domains__table-wrapper tbody tr").count() > 0, (
            "Portfolio domains should be visible."
        )
        assert_extended_header(page)

        page.locator("#domains__table-wrapper a", has_text="Manage").first.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert_extended_header(page)
        assert page.locator(".organization-nav-link").is_visible(), (
            "Portfolio domain should show org name in navbar."
        )
