"""E2E regression tests: Portfolio User with Requester Permissions (User 3).

User 3 setup (created by dev_auto_login persona=portfolio_user_requester_3):
  Email:    regressiontest+3@gmail.com
  Role:     Basic member - domain manager and requester
  Portfolio: 1 portfolio
  Permissions: Can view domains and make requests
  Assigned Domains: At least 1 domain in portfolio

Run:
  cd e2e
  pytest test_portfolio_user_requester.py -v
  pytest test_portfolio_user_requester.py -v --headed
  pytest test_portfolio_user_requester.py -v --headed --slowmo 600
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
    continue_wizard_step,
)

logger = logging.getLogger(__name__)


class TestPortfolioUserRequester:
    """Regression tests for the portfolio user with requester permissions (User 3)."""

    @staticmethod
    def _login(page, next_path="/"):
        dev_auto_login(page, "portfolio_user_requester_3", next_path)

    @staticmethod
    def _fill_domain_request_form(page, requested_domain="requestertestdomain"):
        """Fill the portfolio domain request wizard.

        Portfolio wizard steps differ from the legacy wizard:
          portfolio_requesting_entity → dotgov_domain → purpose →
          portfolio_additional_details → requirements → review

        Caller must already be on /request/start/. Django wizard prefixes all
        field names as <step_name>-<field_name>.
        """
        page.locator("button[name='submit_button'][value='intro_acknowledge']").click()
        page.wait_for_load_state("networkidle")

        page.locator(
            "input[name='portfolio_requesting_entity-requesting_entity_is_suborganization'][value='False']"
        ).dispatch_event("click")
        continue_wizard_step(page)

        page.locator("input[name='dotgov_domain-requested_domain']").fill(requested_domain)
        continue_wizard_step(page)

        page.locator("textarea[name='purpose-purpose']").fill(
            "Portfolio requester E2E regression test domain request."
        )
        continue_wizard_step(page)

        # Use evaluate() here because the hidden radio doesn't respond to dispatch_event reliably
        # in some Chromium builds — evaluate triggers the click directly on the DOM node.
        page.evaluate("""
            const radio = document.querySelector(
                "input[name='portfolio_additional_details-has_anything_else_text'][value='False']"
            );
            if (radio) { radio.click(); }
        """)
        continue_wizard_step(page)

        policy_checkbox = page.locator("input[name='requirements-is_policy_acknowledged']")
        if policy_checkbox.count() > 0:
            policy_checkbox.dispatch_event("click")
            continue_wizard_step(page)

        submit_link = page.locator("a[href='#toggle-submit-domain-request']")
        if submit_link.is_visible():
            submit_link.click()
            page.wait_for_selector("#domain-request-form-submit-button", state="visible", timeout=5000)
            page.locator("#domain-request-form-submit-button").click()
            page.wait_for_load_state("networkidle")

    def test_basic_member_with_requester_permissions_home_page(self, video_page):
        """Portfolio home shows both tabs and the Start a new domain request option."""
        page = video_page
        hide_debug_toolbar(page)
        self._login(page, next_path="/domains/")

        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Expected portfolio home page."
        )

        nav = page.get_by_label("Primary navigation")
        assert nav.get_by_role("link", name="Domains", exact=True).is_visible(), (
            "Domains tab should be visible."
        )
        assert (
            nav.get_by_role("button", name="Domain requests").is_visible()
            or nav.get_by_role("link", name="Domain requests", exact=True).is_visible()
        ), "Domain requests tab should be visible."

        if nav.get_by_role("button", name="Domain requests").is_visible():
            nav.get_by_role("button", name="Domain requests").click()
            page.get_by_role("link", name="Domain requests").first.click()
        else:
            nav.get_by_role("link", name="Domain requests", exact=True).click()
        page.wait_for_load_state("networkidle")
        assert page.url.startswith(f"{BASE_URL}/requests/") or page.locator("h1").first.is_visible(), (
            "Should be able to access the domain requests tab."
        )

        assert (
            page.locator("a", has_text="Start a new domain request").is_visible()
            or page.locator("button", has_text="Start a new domain request").is_visible()
        ), "Start a new domain request should be visible for users with requester permissions."

        assert_extended_header(page)
        assert_portfolio_footer(page)

    def test_portfolio_user_can_create_domain_request(self, video_page):
        """User 3 can fill the portfolio domain request wizard and submit successfully."""
        page = video_page
        hide_debug_toolbar(page)
        self._login(page, next_path="/requests/")

        page.goto(f"{BASE_URL}/request/start/")
        page.wait_for_load_state("networkidle")

        assert page.locator("form").is_visible(), (
            "Domain request creation form should load."
        )
        assert_extended_header(page)

        requested_domain = "requestertestdomain"
        self._fill_domain_request_form(page, requested_domain)

        assert (
            page.locator("h1", has_text="Thanks for your domain request!").is_visible()
            or page.locator("text=Thanks for your domain request").is_visible()
        ), "Form submission should show the confirmation page."

        page.goto(f"{BASE_URL}/requests/")
        page.wait_for_load_state("networkidle")

        wait_for_table_rows(page, "domain-requests__table-wrapper")
        requests_table = page.locator("#domain-requests__table-wrapper tbody")
        assert requests_table.locator("td", has_text=requested_domain).first.is_visible(), (
            f"New request '{requested_domain}' should appear in the table."
        )
