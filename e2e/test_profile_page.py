"""E2E regression tests: User Profile Page.

Scenario: A user can log in (via dev auto-login bypass) and see / edit their profile page.

Run:
  cd e2e
  pip install -r requirements.txt
  playwright install chromium
  pytest test_profile_page.py -v
  pytest test_profile_page.py -v --headed
  pytest test_profile_page.py -v --headed --slowmo 800
"""

import logging
import pytest
from utils import BASE_URL

logger = logging.getLogger(__name__)

AUTO_LOGIN_URL = f"{BASE_URL}/dev-auto-login/"

# Axe-core impact levels that are hard failures; moderate/minor are logged only.
_BLOCKING_IMPACT_LEVELS = {"critical", "serious"}


class TestProfilePage:
    """Regression tests for the user profile page (/user-profile).

    All tests authenticate via the dev-only auto-login bypass, which creates
    (or reuses) a local test user and logs them in through Django's session
    auth — bypassing login.gov while using the real session machinery.
    """

    @staticmethod
    def _login_and_go_to_profile(page):
        page.goto(f"{AUTO_LOGIN_URL}?next=/user-profile")
        page.wait_for_load_state("networkidle")

    def test_user_can_see_profile_page(self, video_page):
        """After auto-login the user lands on /user-profile with the expected heading and form fields."""
        page = video_page
        self._login_and_go_to_profile(page)

        assert "/user-profile" in page.url, (
            f"Expected /user-profile but got: {page.url}\n"
            "Check that the app is running and ALLOW_AUTO_LOGIN=True is set."
        )
        assert page.locator("h1", has_text="Your profile").is_visible()
        assert "Edit your User Profile" in page.title()
        assert page.locator("h2", has_text="Contact information").is_visible()
        assert page.locator("input#id_first_name").is_visible()
        assert page.locator("input#id_last_name").is_visible()
        assert page.locator("input#id_email").is_visible()

    def test_profile_page_not_redirect_to_login(self, video_page):
        """After auto-login the browser must not be redirected to the login.gov OIDC flow."""
        page = video_page
        self._login_and_go_to_profile(page)

        assert "openid" not in page.url, f"Unexpected OIDC redirect: {page.url}"
        assert "identitysandbox" not in page.url, f"Unexpected sandbox redirect: {page.url}"
        assert "login.gov" not in page.url, f"Unexpected login.gov redirect: {page.url}"

    def test_profile_page_accessibility(self, video_page, axe):
        """Runs axe-core against the profile page; hard-fails on critical/serious violations."""
        page = video_page
        self._login_and_go_to_profile(page)

        # Scope to #main-content to avoid pre-existing violations in shared footer/toolbar.
        results = axe.run(page, context="#main-content")

        all_violations = results.response["violations"]
        blocking = [v for v in all_violations if v.get("impact") in _BLOCKING_IMPACT_LEVELS]
        non_blocking = [v for v in all_violations if v.get("impact") not in _BLOCKING_IMPACT_LEVELS]

        if non_blocking:
            logger.warning("%d non-blocking accessibility issue(s) found:", len(non_blocking))
            for v in non_blocking:
                logger.warning("  [%s] %s: %s", v.get("impact"), v.get("id"), v.get("description"))
                for node in v.get("nodes", [])[:2]:
                    logger.warning("    Target: %s", node.get("target"))

        if blocking:
            pytest.fail(
                f"{len(blocking)} blocking (critical/serious) accessibility violation(s) found:\n\n"
                + results.generate_report()
            )

    def test_profile_form_can_be_filled_and_saved(self, video_page):
        """Filling and saving the profile form shows the success banner."""
        page = video_page
        self._login_and_go_to_profile(page)

        page.locator("input#id_first_name").fill("Regression")
        page.locator("input#id_last_name").fill("Tester")
        page.locator("input#id_title").fill("QA Engineer")
        page.locator("input#id_phone").fill("+12025550199")

        page.locator("button[type='submit']", has_text="Save").click()
        page.wait_for_load_state("networkidle")

        success_banner = page.locator(".usa-alert--success .usa-alert__body")
        assert success_banner.is_visible(), (
            "Expected a success alert after saving the profile."
        )
        assert "Your profile has been updated." in success_banner.inner_text()
