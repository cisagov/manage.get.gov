from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model

from api.tests.common import less_console_noise_decorator
from registrar.models.domain import Domain
from registrar.models.user_domain_role import UserDomainRole
from registrar.views.domain import DomainNameserversView

from .common import MockEppLib  # type: ignore
from unittest.mock import patch
from django.urls import reverse

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

    def test_domain_request_form_not_logged_in(self):
        """Domain request form not accessible without a logged-in user."""
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
        # delete any domain requests too
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
        Domain.objects.all().delete()
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

    def side_effect_raise_value_error(self):
        """Side effect that raises a 500 error"""
        raise ValueError("Some error")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment_raises_500_and_shows_banner(self):
        """Tests if the non-prod banner is still shown on a 500"""
        fake_domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # Add a role
        fake_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER
        )

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"pk": fake_domain.id}),
                )

                # Check that a 500 response is returned
                self.assertEqual(contact_page_500.status_code, 500)

                self.assertContains(contact_page_500, "You are on a test site.")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=True)
    def test_production_environment_raises_500_and_doesnt_show_banner(self):
        """Test if the non-prod banner is not shown on production when a 500 is raised"""

        fake_domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # Add a role
        fake_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER
        )

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"pk": fake_domain.id}),
                )

                # Check that a 500 response is returned
                self.assertEqual(contact_page_500.status_code, 500)

                self.assertNotContains(contact_page_500, "You are on a test site.")
