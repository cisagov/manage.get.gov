"""E2E regression tests: Legacy User Full Experience.

User 1 setup (created by dev_auto_login persona=legacy_user_1):
  Email:    regressiontest+1@gmail.com
  Domains:  donutdefenders.gov, alienoutpost.gov, alicornalliance.gov  (all READY)
  Request:  sprinkledonut.gov  (SUBMITTED)

Run:
  cd e2e
  pytest test_legacy_user.py -v
  pytest test_legacy_user.py -v --headed
  pytest test_legacy_user.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import (
    BASE_URL,
    assert_basic_footer,
    assert_basic_header,
    hide_debug_toolbar,
    wait_for_table_rows,
    continue_wizard_step,
)

logger = logging.getLogger(__name__)


class TestLegacyUserFullExperience:
    """Single recorded end-to-end test for the Legacy User experience.

    Executes all Suite 1 scenarios in one continuous session with video
    recording for full click-and-navigation replay.
    """

    @staticmethod
    def _login(page, next_path="/"):
        dev_auto_login(page, "legacy_user_1", next_path)

    @staticmethod
    def _assert_no_org_in_header(page):
        """The header must not display any organisation name."""
        assert not page.locator(".usa-nav__org-name").is_visible(), (
            "Org name should not be visible in the header for legacy users."
        )

    @staticmethod
    def _assert_org_page_blocked(page):
        """Assert organization page access is blocked by 403 or a redirect to home."""
        if page.url.startswith(f"{BASE_URL}/your-organizations"):
            assert (
                page.locator("text=403").is_visible()
                or page.locator("text=Access Denied").is_visible()
                or page.locator("text=Forbidden").is_visible()
            ), "Organization page should be blocked with 403-type messaging."
        else:
            assert page.url == f"{BASE_URL}/" or page.locator(
                "h1", has_text="Manage your domains"
            ).is_visible(), (
                "Organization page access should block and redirect to home if 403 is not shown."
            )

    @staticmethod
    def _fill_domain_request_form(page, requested_domain="newtestdomain"):
        """Fill the domain request wizard for a city-type org.

        Caller must already be on /request/start/. Uses the city org path (non-federal,
        non-tribal). USWDS radio tiles use opacity:0 so dispatch_event bypasses visibility checks.
        Django wizard prefixes all field names as <step_name>-<field_name>.
        """
        page.locator("button[name='submit_button'][value='intro_acknowledge']").click()
        page.wait_for_load_state("networkidle")

        page.locator(
            "input[name='generic_org_type-generic_org_type'][value='city']"
        ).dispatch_event("click")
        continue_wizard_step(page)

        page.locator(
            "input[name='organization_election-is_election_board'][value='False']"
        ).dispatch_event("click")
        continue_wizard_step(page)

        page.locator("input[name='organization_contact-organization_name']").fill("Test City Government")
        page.locator("input[name='organization_contact-address_line1']").fill("123 Main Street")
        page.locator("input[name='organization_contact-city']").fill("Testville")
        page.locator("select[name='organization_contact-state_territory']").select_option("CA")
        page.locator("input[name='organization_contact-zipcode']").fill("90210")
        continue_wizard_step(page)

        about_field = page.locator("textarea[name='about_your_organization-about_your_organization']")
        if about_field.is_visible():
            about_field.fill("A test city government providing essential municipal services.")
            continue_wizard_step(page)

        page.locator("input[name='senior_official-first_name']").fill("John")
        page.locator("input[name='senior_official-last_name']").fill("Doe")
        page.locator("input[name='senior_official-title']").fill("Mayor")
        page.locator("input[name='senior_official-email']").fill("john.doe@testcity.gov")
        continue_wizard_step(page)

        if page.url.endswith("current_sites/"):
            continue_wizard_step(page)

        page.locator("input[name='dotgov_domain-requested_domain']").fill(requested_domain)
        continue_wizard_step(page)

        page.locator("textarea[name='purpose-purpose']").fill(
            "E2E regression test domain request for automated testing purposes."
        )
        continue_wizard_step(page)

        has_other = page.locator("input[name='other_contacts-has_other_contacts'][value='False']")
        if has_other.count() > 0:
            has_other.dispatch_event("click")
            rationale = page.locator("textarea[name='other_contacts-no_other_contacts_rationale']")
            rationale.wait_for(state="visible", timeout=5000)
            rationale.fill("No other contacts are needed for this test request.")
            continue_wizard_step(page)

        cisa_rep = page.locator("input[name='additional_details-has_cisa_representative'][value='False']")
        if cisa_rep.count() > 0:
            cisa_rep.dispatch_event("click")
        anything_else = page.locator("input[name='additional_details-has_anything_else_text'][value='False']")
        if anything_else.count() > 0:
            anything_else.dispatch_event("click")
        if cisa_rep.count() > 0 or anything_else.count() > 0:
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

    def test_legacy_user_full_experience(self, video_page):
        """Complete legacy user flow: home page, domain management, profile, and domain request.

        Steps:
          1.  Login and verify the legacy home page (domains + requests visible, single navbar).
          2.  Manage donutdefenders.gov — verify senior official and security email tabs.
          3.  Navigate to /your-organizations/ — verify access is blocked.
          4.  Open profile page from the username dropdown.
          5.  Return home and manage the sprinkledonut.gov domain request.
          6.  Navigate to the create new domain request flow.
          7.  Fill in all form steps and submit.
          8.  Verify the confirmation page, then return home and confirm the new request appears.
        """
        page = video_page
        hide_debug_toolbar(page)

        self._login(page, next_path="/")

        assert page.locator("h1", has_text="Manage your domains").is_visible(), (
            "Expected 'Manage your domains' heading on the legacy home page."
        )

        wait_for_table_rows(page, "domains__table-wrapper")
        domains_table = page.locator("#domains__table-wrapper tbody")
        assert domains_table.locator("td", has_text="donutdefenders.gov").is_visible(), (
            "donutdefenders.gov should be visible in the domains table."
        )
        assert domains_table.locator("td", has_text="alienoutpost.gov").is_visible(), (
            "alienoutpost.gov should be visible in the domains table."
        )
        assert domains_table.locator("td", has_text="alicornalliance.gov").is_visible(), (
            "alicornalliance.gov should be visible in the domains table."
        )

        wait_for_table_rows(page, "domain-requests__table-wrapper")
        requests_table = page.locator("#domain-requests__table-wrapper tbody")
        assert requests_table.locator("td", has_text="sprinkledonut.gov").is_visible(), (
            "sprinkledonut.gov should be visible in the domain requests table."
        )

        assert_basic_header(page)
        assert page.locator(".usa-nav__username").is_visible(), (
            "User email should appear in the nav."
        )
        self._assert_no_org_in_header(page)
        assert_basic_footer(page)

        # Step 2: Manage donutdefenders.gov
        page.locator("#domains__table-wrapper a", has_text="Manage").first.click()
        page.wait_for_load_state("networkidle")

        assert_basic_header(page)
        assert page.locator(".usa-nav__username").is_visible(), (
            "User email should still appear in the nav on the domain detail page."
        )
        assert page.locator("h3", has_text="Senior official").is_visible(), (
            "Legacy domain detail page must display the 'Senior official' section."
        )

        page.get_by_role("link", name="Senior official", exact=True).click()
        page.wait_for_load_state("networkidle")
        assert (
            page.locator("input[name='first_name']").is_visible()
            or page.locator("h1", has_text="Senior official").is_visible()
        ), "Senior official details should be shown."

        page.get_by_role("link", name="Security email", exact=True).click()
        page.wait_for_load_state("networkidle")
        assert page.locator("input[name='security_email']").is_visible(), (
            "Security email field should be present."
        )

        assert_basic_footer(page)

        # Step 3: Navigate to /your-organizations/ and verify access is blocked
        page.goto(f"{BASE_URL}/your-organizations/")
        page.wait_for_load_state("networkidle")

        self._assert_org_page_blocked(page)
        assert_basic_footer(page)

        # Step 4: Open the profile page from the username dropdown
        page.goto(f"{BASE_URL}/")
        wait_for_table_rows(page, "domains__table-wrapper")

        page.locator(".usa-nav__username").click()
        page.get_by_label("Primary navigation").get_by_role(
            "link", name="Your profile"
        ).first.click()
        page.wait_for_load_state("networkidle")

        assert (
            page.locator("h1", has_text="Your profile").is_visible()
            or page.locator("text=Your profile").is_visible()
        ), "Profile page should load."

        assert_basic_header(page)
        self._assert_no_org_in_header(page)

        email_field = page.locator("input[name='email']")
        if email_field.is_visible():
            assert (
                email_field.get_attribute("readonly") is not None
                or email_field.get_attribute("disabled") is not None
            ), "Email field should be readonly or disabled."

        assert_basic_footer(page)

        # Step 5: Return home and manage the sprinkledonut.gov domain request
        page.goto(f"{BASE_URL}/")
        wait_for_table_rows(page, "domain-requests__table-wrapper")

        page.locator("#domain-requests__table-wrapper a", has_text="Manage").first.click()
        page.wait_for_load_state("networkidle")

        assert (
            page.locator("h1", has_text="Domain request").is_visible()
            or page.locator("text=Domain request").is_visible()
        ), "Domain request summary page should load."

        assert_basic_header(page)
        self._assert_no_org_in_header(page)
        assert_basic_footer(page)

        # Step 6: Navigate to the create new domain request flow
        page.goto(f"{BASE_URL}/request/start/")
        page.wait_for_load_state("networkidle")

        assert page.locator("form").is_visible(), (
            "Domain request intro form should be visible at /request/start/."
        )
        assert_basic_header(page)
        self._assert_no_org_in_header(page)
        assert_basic_footer(page)

        # Step 7: Fill in all wizard steps and submit
        requested_domain = "newtestdomain"
        self._fill_domain_request_form(page, requested_domain)

        # Step 8: Verify confirmation page and check new request on home
        assert (
            page.locator("h1", has_text="Thanks for your domain request!").is_visible()
            or page.locator("text=Thanks for your domain request").is_visible()
        ), "Should show 'Thanks for your domain request!' after submitting."

        status_link = page.get_by_role("link", name="check the status")
        if status_link.is_visible():
            status_link.click()
        else:
            page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        wait_for_table_rows(page, "domain-requests__table-wrapper")
        requests_table = page.locator("#domain-requests__table-wrapper tbody")
        assert requests_table.locator("td", has_text=requested_domain).first.is_visible(), (
            f"New request '{requested_domain}' should be visible in the domain requests table."
        )
        assert requests_table.locator("td", has_text="Submitted").first.is_visible(), (
            "New request should have status 'Submitted'."
        )

        logger.debug("Legacy user full experience completed.")
