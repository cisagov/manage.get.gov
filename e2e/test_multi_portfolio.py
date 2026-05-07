"""E2E regression tests: Multi-Portfolio Admin Experience (User 7).

User 7 setup (created by dev_auto_login persona=multi_portfolio_admin_7):
  Email:    regressiontest+7@gmail.com
  Role:     Organization admin in 2 different portfolios
  Portfolios: 2 portfolios (Test Portfolio 7A, Test Portfolio 7B)
  Note: multiple_portfolios waffle flag is enabled by the persona factory

Run:
  cd e2e
  pytest test_multi_portfolio.py -v
  pytest test_multi_portfolio.py -v --headed
  pytest test_multi_portfolio.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import BASE_URL, assert_extended_header, hide_debug_toolbar, select_portfolio

logger = logging.getLogger(__name__)


class TestMultiPortfolioAdmin:
    """Regression tests for the multi-portfolio admin experience (User 7)."""

    @staticmethod
    def _login(page, next_path="/"):
        dev_auto_login(page, "multi_portfolio_admin_7", next_path)

    def test_multi_portfolio_user_portfolio_selector(self, video_page):
        """Login presents the portfolio selector, and selecting one lands on the portfolio home."""
        page = video_page
        self._login(page, next_path="/")
        hide_debug_toolbar(page)

        assert (
            page.url.startswith(f"{BASE_URL}/your-organizations")
            or page.locator("h1", has_text="Your organizations").is_visible()
        ), "Portfolio selection page (/your-organizations/) should be displayed."

        portfolio_buttons = page.locator("button.usa-card__container")
        assert portfolio_buttons.count() >= 2, (
            "At least 2 portfolio buttons should be listed on the selection page."
        )

        select_portfolio(page, index=0)

        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Should be on the portfolio home page after selection."
        )
        assert_extended_header(page)
        assert page.locator(".organization-nav-link").is_visible(), (
            "Organization name should be visible in the nav after selecting a portfolio."
        )

    def test_multi_portfolio_user_switch_between_portfolios(self, video_page):
        """Switching portfolios via the Organizations dropdown updates the org name."""
        page = video_page
        self._login(page, next_path="/")
        hide_debug_toolbar(page)

        select_portfolio(page, index=0)
        first_org_name = page.locator(".organization-nav-link").first.text_content().strip()

        orgs_button = page.locator("button#organizations-menu").first
        assert orgs_button.is_visible(), (
            "Organizations dropdown button should be visible for multi-portfolio users."
        )

        orgs_button.click()
        page.wait_for_selector("#organizations-submenu", state="visible", timeout=5_000)
        hide_debug_toolbar(page)

        submenu_buttons = page.locator("#organizations-submenu button.organization-button")
        assert submenu_buttons.count() >= 2, (
            "Both portfolios should appear in the organizations dropdown."
        )

        submenu_buttons.nth(1).click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        second_org_name = page.locator(".organization-nav-link").first.text_content().strip()
        assert second_org_name != first_org_name, (
            f"Org name should change after switching. Got '{second_org_name}' vs '{first_org_name}'"
        )
        assert_extended_header(page)

    def test_multi_portfolio_admin_your_organizations_page(self, video_page):
        """After selecting a portfolio, /your-organizations/ still lists all portfolios."""
        page = video_page
        self._login(page, next_path="/")
        hide_debug_toolbar(page)

        select_portfolio(page, index=0)
        hide_debug_toolbar(page)

        page.goto(f"{BASE_URL}/your-organizations/")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

        assert page.locator("h1", has_text="Your organizations").is_visible(), (
            "/your-organizations/ should show the 'Your organizations' heading."
        )

        portfolio_buttons = page.locator("button.usa-card__container")
        assert portfolio_buttons.count() >= 2, (
            "Both portfolios should be listed on /your-organizations/."
        )

        select_portfolio(page, index=1)

        assert page.url.startswith(f"{BASE_URL}/domains/") or page.locator("h1").first.is_visible(), (
            "Should land on the portfolio home after selecting from /your-organizations/."
        )
        assert_extended_header(page)
