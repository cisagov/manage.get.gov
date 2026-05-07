"""Shared Playwright fixtures for get.gov E2E regression tests."""

import logging
import os
import pytest
from axe_playwright_python.sync_playwright import Axe

from utils import BASE_URL, hide_debug_toolbar

logger = logging.getLogger(__name__)

AUTO_LOGIN_URL = f"{BASE_URL}/dev-auto-login/"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
VIDEO_DIR = os.path.join(os.path.dirname(__file__), "videos")


@pytest.fixture(scope="session", autouse=True)
def ensure_output_dirs():
    """Create screenshots/ and videos/ output directories once per session."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
def axe():
    """Axe-core accessibility runner — inject and run against any Playwright page."""
    return Axe()


@pytest.fixture
def authenticated_page(page):
    """Return a Playwright page authenticated as the generic E2E test user."""
    page.goto(f"{AUTO_LOGIN_URL}?persona=generic&next=/user-profile")
    page.wait_for_load_state("networkidle")
    return page


def dev_auto_login(page, persona: str, next_path: str = "/"):
    """Navigate through dev-auto-login for a named persona and fail if it is unavailable."""
    login_url = f"{AUTO_LOGIN_URL}?persona={persona}&next={next_path}"
    response = page.goto(login_url)
    page.wait_for_load_state("networkidle")

    if response is None:
        pytest.fail(
            f"Dev auto-login persona '{persona}' did not return a response. "
            "Ensure /dev-auto-login/ is enabled and the test infrastructure supports this persona."
        )

    if response.status is not None and response.status >= 400:
        pytest.fail(
            f"Dev auto-login persona '{persona}' returned HTTP status {response.status}. "
            "The dev-auto-login endpoint or persona configuration is broken."
        )

    if page.url.startswith(f"{BASE_URL}/openid/login") or page.url.startswith(f"{BASE_URL}/login"):
        pytest.fail(
            f"Dev auto-login persona '{persona}' redirected to login instead of bypassing auth. "
            "The dev-auto-login bypass is not functioning for this persona."
        )

    if page.url.startswith(AUTO_LOGIN_URL):
        pytest.fail(
            f"Dev auto-login persona '{persona}' did not complete the redirect from the auto-login endpoint."
        )

    return page


@pytest.fixture
def video_page(browser, request):
    """
    Return a Playwright page configured for video recording.

    The video is saved to videos/<test_name>.webm when the test finishes,
    regardless of pass or fail. On failure, a screenshot is also saved by
    the pytest_runtest_makereport hook below.

    Each test is responsible for navigating to the appropriate persona URL
    before interacting with the page.
    """
    context = browser.new_context(
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1280, "height": 720},
    )
    page = context.new_page()

    yield page

    video = page.video
    context.close()
    if video:
        try:
            original_path = video.path()
            safe_name = (
                request.node.name
                .replace("[", "_")
                .replace("]", "")
                .replace(" ", "_")
            )
            new_path = os.path.join(VIDEO_DIR, f"{safe_name}.webm")
            os.rename(original_path, new_path)
            logger.debug("Video saved: %s", new_path)
        except Exception as exc:
            logger.warning("Could not rename video: %s", exc)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Save a failure screenshot for any test that has a page or video_page fixture."""
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    safe_name = (
        item.name
        .replace("[", "_")
        .replace("]", "")
        .replace(" ", "_")
    )
    path = os.path.join(SCREENSHOT_DIR, f"FAILED_{safe_name}.png")

    pg = (
        item.funcargs.get("video_page")
        or item.funcargs.get("page")
        or item.funcargs.get("authenticated_page")
    )
    if pg is not None:
        try:
            pg.screenshot(path=path, full_page=True)
            logger.debug("Failure screenshot: %s", path)
        except Exception as exc:
            logger.warning("Could not take failure screenshot: %s", exc)
