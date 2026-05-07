"""E2E regression tests: Permission-Based UI Rendering.

Run:
  cd e2e
  pytest test_permission_ui.py -v
  pytest test_permission_ui.py -v --headed
  pytest test_permission_ui.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import BASE_URL, assert_extended_header, hide_debug_toolbar

logger = logging.getLogger(__name__)


class TestPermissionUI:
    """Regression tests for permission-based UI rendering."""

    @staticmethod
    def _login_basic(page, next_path="/domains/"):
        dev_auto_login(page, "portfolio_user_2", next_path)

    @staticmethod
    def _login_requester(page, next_path="/domains/"):
        dev_auto_login(page, "portfolio_user_requester_3", next_path)

    @staticmethod
    def _login_admin(page, next_path="/domains/"):
        dev_auto_login(page, "org_admin_4", next_path)

    def test_basic_member_cannot_see_admin_controls(self, video_page):
        """Basic member does not see the Members link or Settings, but does see Domains and Requests."""
        page = video_page
        self._login_basic(page, next_path="/domains/")
        hide_debug_toolbar(page)

        nav = page.get_by_label("Primary navigation")

        assert not nav.get_by_role("link", name="Members", exact=True).is_visible(), (
            "Members link should NOT be visible for basic members."
        )
        assert not page.locator("a", has_text="Settings").is_visible(), (
            "Settings should not be accessible for basic members."
        )
        assert nav.get_by_role("link", name="Domains", exact=True).is_visible(), (
            "Domains link should be visible."
        )
        assert nav.get_by_role("link", name="Domain requests", exact=True).is_visible(), (
            "Domain requests link should be visible."
        )

    def test_admin_can_see_admin_controls(self, video_page):
        """Org admin sees the Members link and the Add a new member button on the members page."""
        page = video_page
        self._login_admin(page, next_path="/domains/")
        hide_debug_toolbar(page)

        nav = page.get_by_label("Primary navigation")
        assert nav.get_by_role("link", name="Members", exact=True).is_visible(), (
            "Members link should be visible for org admin."
        )

        nav.get_by_role("link", name="Members", exact=True).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.url.startswith(f"{BASE_URL}/members") or page.locator("h1").first.is_visible(), (
            "Member management page should load."
        )

        add_member = page.locator("a", has_text="Add a new member").or_(
            page.locator("button", has_text="Add a new member")
        )
        assert add_member.is_visible(), (
            "Add a new member control should be visible for admin."
        )

    def test_requester_can_start_domain_request(self, video_page):
        """Requester sees the Start a new domain request button; basic member does not."""
        page = video_page

        # User 3 (requester)
        self._login_requester(page, next_path="/requests/")
        hide_debug_toolbar(page)

        start_button = page.locator("button", has_text="Start a new domain request")
        assert start_button.is_visible(), (
            "Start a new domain request should be visible for users with requester permissions."
        )

        page.goto(f"{BASE_URL}/request/start/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        assert page.locator("form").is_visible(), (
            "Domain request form should load for requesters."
        )

        # User 2 (basic member, no EDIT_REQUESTS)
        self._login_basic(page, next_path="/domains/")
        hide_debug_toolbar(page)

        page.goto(f"{BASE_URL}/no-organization-requests/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        start_button_basic = page.locator("button", has_text="Start a new domain request")
        assert not start_button_basic.is_visible(), (
            "Start a new domain request should NOT be visible for non-requester users."
        )
