"""Shared helper utilities for E2E regression tests."""

import os

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")


def hide_debug_toolbar(page):
    """Hide the Django Debug Toolbar overlay so it doesn't intercept pointer events."""
    try:
        page.evaluate("""
            const bar = document.getElementById('djDebug');
            if (bar) { bar.style.display = 'none'; }
            const handle = document.getElementById('djdt-hide-button');
            if (handle) { handle.style.display = 'none'; }
        """)
    except Exception:
        pass


def wait_for_table_rows(page, table_id: str, timeout: int = 15_000):
    """Wait for at least one data row in a JS-populated table."""
    page.wait_for_selector(f"#{table_id} tbody tr", timeout=timeout)


def assert_basic_header(page):
    """Assert the single-navbar (legacy) header is present and the extended header is not."""
    assert page.locator("header.usa-header--basic").is_visible(), (
        "Expected basic header (usa-header--basic) for legacy users."
    )
    assert not page.locator("header.usa-header--extended").is_visible(), (
        "Extended header should NOT be visible for legacy users."
    )


def assert_extended_header(page):
    """Assert the dual-navbar (portfolio) header is present and the basic header is not."""
    assert page.locator("header.usa-header--extended").is_visible(), (
        "Expected extended header (usa-header--extended) for portfolio users."
    )
    assert not page.locator("header.usa-header--basic").is_visible(), (
        "Basic header should NOT be visible for portfolio users."
    )


def assert_basic_footer(page):
    """Assert legacy footer contains only Home and Your profile, with no portfolio links."""
    footer = page.locator(".usa-footer__address")
    assert footer.locator("a", has_text="Home").is_visible(), (
        "Footer must contain a 'Home' link for legacy users."
    )
    assert footer.locator("a", has_text="Your profile").is_visible(), (
        "Footer must contain a 'Your profile' link for legacy users."
    )
    assert not footer.locator("a", has_text="Domains").is_visible(), (
        "Footer must NOT contain a 'Domains' link for legacy users."
    )
    assert not footer.locator("a", has_text="Domain requests").is_visible(), (
        "Footer must NOT contain a 'Domain requests' link for legacy users."
    )
    assert not footer.locator("a", has_text="Organization").is_visible(), (
        "Footer must NOT contain an 'Organization' link for legacy users."
    )


def assert_portfolio_footer(page):
    """Assert portfolio footer contains Domains, Domain requests, Organization, and Your profile."""
    footer = page.locator(".usa-footer__address")
    assert footer.locator("a", has_text="Domains").is_visible(), (
        "Footer must contain a 'Domains' link for portfolio users."
    )
    assert footer.locator("a", has_text="Domain requests").is_visible(), (
        "Footer must contain a 'Domain requests' link for portfolio users."
    )
    assert footer.locator("a", has_text="Organization").is_visible(), (
        "Footer must contain an 'Organization' link for portfolio users."
    )
    assert footer.locator("a", has_text="Your profile").is_visible(), (
        "Footer must contain a 'Your profile' link for portfolio users."
    )


def select_portfolio(page, index: int = 0):
    """Select the nth portfolio card on the /your-organizations/ page."""
    page.locator("button.usa-card__container").nth(index).click()
    page.wait_for_load_state("networkidle")
    hide_debug_toolbar(page)


def continue_wizard_step(page):
    """Submit the current domain request wizard step and wait for the next page."""
    page.locator("button[name='submit_button'][value='next']").click()
    page.wait_for_load_state("networkidle")
