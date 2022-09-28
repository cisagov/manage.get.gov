from django.test import Client, TestCase
from django.contrib.auth import get_user_model


class HealthTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OK")


class LoggedInTests(TestCase):
    def setUp(self):
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )
        self.client.force_login(self.user)

    def test_edit_profile(self):
        response = self.client.get("/edit_profile/")
        self.assertContains(response, "Display Name")
