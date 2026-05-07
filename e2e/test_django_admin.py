"""E2E regression tests: Django Admin Analyst Experience (User 8).

User 8 setup (created by dev_auto_login persona=django_admin_analyst_8):
  Email:    regressiontest+8@example.com
  Role:     is_staff=True, is_superuser=True, cisa_analysts_group
  Data:     Many domain requests (various statuses/org types) + approved domains

Run:
  cd e2e
  pytest test_django_admin.py -v
  pytest test_django_admin.py -v --headed
  pytest test_django_admin.py -v --headed --slowmo 600
"""

import logging
import pytest
from conftest import dev_auto_login
from utils import BASE_URL, hide_debug_toolbar

logger = logging.getLogger(__name__)

WORKFLOW_REQUEST_NAME = "a8city1.gov"
SEARCH_DOMAIN_NAME = "a8citya.gov"
WAIT = 1_000


class TestDjangoAdminAnalyst:
    """Regression tests for the Django Admin Analyst experience (User 8)."""

    _ADMIN_URL = f"{BASE_URL}/admin"
    _DOMAIN_REQUESTS_URL = f"{BASE_URL}/admin/registrar/domainrequest/"
    _DOMAINS_URL = f"{BASE_URL}/admin/registrar/domain/"
    _DOMAIN_INFO_URL = f"{BASE_URL}/admin/registrar/domaininformation/"

    @staticmethod
    def _login(page, next_path="/admin/"):
        dev_auto_login(page, "django_admin_analyst_8", next_path)

    @staticmethod
    def _nav(page, url):
        """Navigate to a URL, wait for network idle, and hide the debug toolbar."""
        page.goto(url)
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)

    @staticmethod
    def _search(page, term, list_url=None):
        """Navigate directly to the admin list with a search query applied.

        Navigating by URL is more reliable than typing in the search bar because
        it avoids race conditions with the Django admin's AJAX-based filtering.
        """
        base = list_url or page.url.split("?")[0]
        page.goto(f"{base.rstrip('/')}/?q={term}")
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

    @staticmethod
    def _click_filter(page, filter_text):
        """Click a standard filter link in the #changelist-filter sidebar."""
        link = page.locator("#changelist-filter a", has_text=filter_text).first
        if link.is_visible():
            link.click()
            page.wait_for_load_state("networkidle")
            hide_debug_toolbar(page)
            page.wait_for_timeout(WAIT)
            return True
        return False

    @staticmethod
    def _click_checkbox_filter(page, filter_text):
        """Click a MultipleChoiceListFilter checkbox-style link in the sidebar."""
        panel = page.locator("#changelist-filter")
        link = panel.locator("[role='menuitemcheckbox']", has_text=filter_text).first
        if not link.is_visible():
            link = panel.locator("a", has_text=filter_text).first
        if link.is_visible():
            link.click()
            page.wait_for_load_state("networkidle")
            hide_debug_toolbar(page)
            page.wait_for_timeout(WAIT)
            return True
        return False

    @staticmethod
    def _reset_filters(page, list_url):
        """Navigate back to the unfiltered list to clear active filter state."""
        page.goto(list_url)
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

    def test_admin_domain_request_workflow(self, video_page):
        """Domain request analyst workflow: assign investigator, set in review, approve.

        Steps:
          1. Login and navigate to the domain requests list.
          2. Search for the target SUBMITTED request.
          3. Open the detail page.
          4. Click "Assign to me" to set self as investigator.
          5. Click "Save and continue editing" to persist the investigator.
          6. Select "In review" from the status dropdown (now available since investigator is set).
          7. Click Save and verify success.
          8. Re-open the request; verify status is "In review".
          9. Change status to "Approved" and save.
         10. Verify the domain now exists in the admin domain table.
         11. Verify a domain information record also exists.
        """
        page = video_page
        self._login(page)
        page.wait_for_timeout(WAIT)

        self._nav(page, self._DOMAIN_REQUESTS_URL)
        self._search(page, WORKFLOW_REQUEST_NAME.replace(".gov", ""))

        assert page.locator("a", has_text=WORKFLOW_REQUEST_NAME).first.is_visible(), (
            f"Expected to find '{WORKFLOW_REQUEST_NAME}' in search results."
        )

        page.locator("a", has_text=WORKFLOW_REQUEST_NAME).first.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

        assert "change" in page.url or "domainrequest" in page.url, (
            "Expected to be on the domain request detail page."
        )

        assign_btn = page.locator("#investigator__assign_self")
        assert assign_btn.is_visible(), (
            "'Assign to me' button should be visible for a superuser."
        )
        assign_btn.click()
        page.wait_for_timeout(WAIT)

        # Save and continue editing so the investigator persists in the DB
        # and the page reloads — the status dropdown will then offer all transitions.
        page.locator("[name='_continue']").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

        # Select "In review" from the dropdown now that the investigator is set.
        page.select_option("#id_status", "in review")
        page.wait_for_timeout(WAIT)

        page.locator("[name='_save']").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

        page_content = page.content()
        assert (
            "was changed successfully" in page_content
            or self._DOMAIN_REQUESTS_URL.rstrip("/") in page.url
        ), "Expected success message or redirect after saving 'In review'."

        # Re-open the request and verify the status shows "In review".
        self._nav(page, self._DOMAIN_REQUESTS_URL)
        self._search(page, WORKFLOW_REQUEST_NAME.replace(".gov", ""))

        assert page.locator("a", has_text=WORKFLOW_REQUEST_NAME).first.is_visible(), (
            f"Expected '{WORKFLOW_REQUEST_NAME}' to still appear after saving 'In review'."
        )

        row_text = page.locator("table#result_list tbody tr").first.text_content() or ""
        assert "In review" in row_text or "in review" in row_text.lower(), (
            f"Expected the row to show 'In review' status. Row: {row_text!r}"
        )

        page.locator("a", has_text=WORKFLOW_REQUEST_NAME).first.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

        assert "In review" in page.content() or "in review" in page.content(), (
            "Expected the detail page to show 'In review' status."
        )

        # Change status to "Approved" and save.
        page.select_option("#id_status", "approved")
        page.wait_for_timeout(WAIT)

        page.locator("[name='_save']").click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

        page_content = page.content()
        assert (
            "was changed successfully" in page_content
            or self._DOMAIN_REQUESTS_URL.rstrip("/") in page.url
        ), "Expected success message or redirect after approving the domain request."

        # Verify the approved domain now exists in the domains table.
        domain_name = WORKFLOW_REQUEST_NAME
        self._search(page, domain_name.replace(".gov", ""), list_url=self._DOMAINS_URL)

        first_row = page.locator("table#result_list tbody tr").first
        assert first_row.is_visible(), (
            f"Expected at least one row in the domains table after searching for '{domain_name}'."
        )
        assert page.locator("a", has_text=domain_name).first.is_visible(), (
            f"Expected domain '{domain_name}' to appear in the domains table after approval."
        )
        logger.debug("Domain '%s' confirmed in domain table after approval.", domain_name)

        # Verify domain information also exists for the approved domain.
        self._search(page, domain_name.replace(".gov", ""), list_url=self._DOMAIN_INFO_URL)

        first_row = page.locator("table#result_list tbody tr").first
        assert first_row.is_visible(), (
            f"Expected at least one row in domain information after searching for '{domain_name}'."
        )
        assert page.locator("a", has_text=domain_name).first.is_visible(), (
            f"Expected domain information for '{domain_name}' to exist after approval."
        )
        logger.debug("Domain information for '%s' confirmed after approval.", domain_name)

    def test_admin_domain_search(self, video_page):
        """Domains table search by domain name."""
        page = video_page
        self._login(page)
        page.wait_for_timeout(WAIT)

        self._nav(page, self._DOMAINS_URL)
        self._search(page, SEARCH_DOMAIN_NAME.replace(".gov", ""))

        assert page.locator("a", has_text=SEARCH_DOMAIN_NAME).first.is_visible(), (
            f"Expected to find domain '{SEARCH_DOMAIN_NAME}' in search results."
        )
        logger.debug("Domain search completed.")

    def test_admin_domain_request_filters(self, video_page):
        """Domain requests sidebar filters — exercises every filter option.

        Covers status, generic org type, federal type, election office,
        rejection reason, and investigator filters.
        """
        page = video_page
        self._login(page)
        page.wait_for_timeout(WAIT)

        self._nav(page, self._DOMAIN_REQUESTS_URL)

        # Status filters
        for label in ["In review", "Action needed", "Approved", "Rejected",
                      "Submitted", "Withdrawn", "Started"]:
            self._reset_filters(page, self._DOMAIN_REQUESTS_URL)
            self._click_checkbox_filter(page, label)
            logger.debug("Domain request status filter '%s' applied.", label)

        # Generic org type filters
        for label in ["Federal", "City", "County", "State or territory",
                      "Tribal", "School district", "Interstate", "Special district"]:
            self._reset_filters(page, self._DOMAIN_REQUESTS_URL)
            self._click_filter(page, label)
            logger.debug("Domain request org type filter '%s' applied.", label)

        # Federal type filters
        for label in ["Executive", "Judicial", "Legislative"]:
            self._reset_filters(page, self._DOMAIN_REQUESTS_URL)
            self._click_filter(page, label)
            logger.debug("Domain request federal type filter '%s' applied.", label)

        # Election office filters
        for label in ["Yes", "No"]:
            self._reset_filters(page, self._DOMAIN_REQUESTS_URL)
            self._click_filter(page, label)
            logger.debug("Domain request election filter '%s' applied.", label)

        # Rejection reason filters
        for label in ["Purpose requirements not met", "Org not eligible for a .gov domain"]:
            self._reset_filters(page, self._DOMAIN_REQUESTS_URL)
            self._click_filter(page, label)
            logger.debug("Domain request rejection filter '%s' applied.", label)

        # Investigator filter
        self._reset_filters(page, self._DOMAIN_REQUESTS_URL)
        analyst_link = page.locator("#changelist-filter a", has_text="Analyst Eight").first
        if analyst_link.is_visible():
            analyst_link.click()
            page.wait_for_load_state("networkidle")
            hide_debug_toolbar(page)
            page.wait_for_timeout(WAIT)
            logger.debug("Domain request investigator filter applied.")

        logger.debug("Domain request filters completed.")

    def test_admin_domain_filters(self, video_page):
        """Domain table sidebar filters — exercises org type, federal type, election, and state."""
        page = video_page
        self._login(page)
        page.wait_for_timeout(WAIT)

        self._nav(page, self._DOMAINS_URL)

        # Generic org type filters
        for label in ["Federal", "City", "County", "State or territory"]:
            self._reset_filters(page, self._DOMAINS_URL)
            self._click_filter(page, label)
            logger.debug("Domain org type filter '%s' applied.", label)

        # Federal type filters
        for label in ["Executive", "Judicial"]:
            self._reset_filters(page, self._DOMAINS_URL)
            self._click_filter(page, label)
            logger.debug("Domain federal type filter '%s' applied.", label)

        # Election office filters
        for label in ["Yes", "No"]:
            self._reset_filters(page, self._DOMAINS_URL)
            self._click_filter(page, label)
            logger.debug("Domain election filter '%s' applied.", label)

        # Domain state filters
        for label in ["ready", "on hold", "unknown", "dns needed", "deleted"]:
            self._reset_filters(page, self._DOMAINS_URL)
            panel = page.locator("#changelist-filter")
            link = panel.locator("a", has_text=label).first
            if not link.is_visible():
                link = panel.locator("a", has_text=label.title()).first
            if link.is_visible():
                link.click()
                page.wait_for_load_state("networkidle")
                hide_debug_toolbar(page)
                page.wait_for_timeout(WAIT)
                logger.debug("Domain state filter '%s' applied.", label)

        logger.debug("Domain filters completed.")

    def test_admin_domain_request_show_more(self, video_page):
        """Collapsible fieldsets on the domain request detail page can all be expanded."""
        page = video_page
        self._login(page)
        page.wait_for_timeout(WAIT)

        self._nav(page, self._DOMAIN_REQUESTS_URL)
        self._search(page, "a8county1")

        assert page.locator("a", has_text="a8county1.gov").first.is_visible(), (
            "Expected to find 'a8county1.gov' domain request."
        )
        page.locator("a", has_text="a8county1.gov").first.click()
        page.wait_for_load_state("networkidle")
        hide_debug_toolbar(page)
        page.wait_for_timeout(WAIT)

        buttons = page.locator("fieldset.collapse--dgfieldset button")
        btn_count = buttons.count()
        assert btn_count > 0, (
            f"Expected at least one 'Show details' button, found {btn_count}."
        )

        for i in range(btn_count):
            btn = buttons.nth(i)
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(WAIT)

        assert "change" in page.url or "domainrequest" in page.url, (
            "Expected to remain on the domain request detail page after expanding fieldsets."
        )
        logger.debug("Show details completed — all fieldsets expanded.")
