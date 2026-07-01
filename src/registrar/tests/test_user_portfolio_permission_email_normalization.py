from django.test import Client, TestCase, override_settings
from django.urls import reverse
from waffle.testutils import override_flag

from api.tests.common import less_console_noise_decorator
from registrar import models
from registrar.models import Portfolio, UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices

from .common import create_superuser


class TestUserPortfolioPermissionEmailNormalization(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.portfolio = Portfolio.objects.create(organization_name="Test Portfolio", requester=self.superuser)
        self.add_url = reverse("admin:registrar_userportfoliopermission_add")

    @less_console_noise_decorator
    def test_save_lowercases_email_and_str_uses_normalized_value(self):
        mixed_case_email = "New.Person@Example.GOV"
        permission = UserPortfolioPermission.objects.create(
            email=mixed_case_email,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            status=UserPortfolioPermission.Status.INVITED,
        )

        permission.refresh_from_db()

        self.assertEqual(permission.email, mixed_case_email.lower())
        self.assertIn(mixed_case_email.lower(), str(permission))
        self.assertNotIn(mixed_case_email, str(permission))

    @less_console_noise_decorator
    @override_flag("user_portfolio_permission_invitations", active=True)
    @override_settings(IS_PRODUCTION=False)
    def test_add_popup_response_uses_lowercase_email(self):
        self.client.force_login(self.superuser)
        mixed_case_email = "New.Person@Example.GOV"
        normalized_email = mixed_case_email.lower()
        models.AllowedEmail.objects.create(email=normalized_email)

        response = self.client.post(
            self.add_url,
            data={
                "user": mixed_case_email,
                "portfolio": self.portfolio.id,
                "role": UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
                "send_email": "",
                "_popup": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(normalized_email, response.content.decode("utf-8"))
        self.assertNotIn(mixed_case_email, response.content.decode("utf-8"))
