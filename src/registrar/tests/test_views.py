from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model

from .common import MockEppLib  # type: ignore


from registrar.models import (
    DomainRequest,
    DomainInformation,
)
import logging

logger = logging.getLogger(__name__)


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        response = self.client.get("/health")
        self.assertContains(response, "OK", status_code=200)

    def test_home_page(self):
        """Home page should NOT be available without a login."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_application_form_not_logged_in(self):
        """Application form not accessible without a logged-in user."""
        response = self.client.get("/request/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=/request/", response.headers["Location"])


class TestWithUser(MockEppLib):
    def setUp(self):
        super().setUp()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )

    def tearDown(self):
        # delete any applications too
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        self.user.delete()


class TestEnvironmentVariablesEffects(TestCase):
    def setUp(self):
        self.client = Client()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        self.user.delete()

    @override_settings(IS_PRODUCTION=True)
    def test_production_environment(self):
        """No banner on prod."""
        home_page = self.client.get("/")
        self.assertNotContains(home_page, "You are on a test site.")

    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment(self):
        """Banner on non-prod."""
        home_page = self.client.get("/")
        self.assertContains(home_page, "You are on a test site.")
