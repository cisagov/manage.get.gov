from django.test import Client, TestCase
from django.contrib.auth.models import User


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        response = self.client.get("/health/")
        self.assertContains(response, "OK", status_code=200)

    def test_home_page(self):
        """Home page should be available without a login."""
        response = self.client.get("/")
        self.assertContains(response, "registrar", status_code=200)
        self.assertContains(response, "log in")

    def test_whoami_page(self):
        """User information appears on the whoami page."""
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        user = User.objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )
        self.client.force_login(user)
        response = self.client.get("/whoami")
        self.assertContains(response, first_name)
        self.assertContains(response, last_name)
        self.assertContains(response, email)

    def test_whoami_page_no_user(self):
        """Whoami page not accessible without a logged-in user."""
        response = self.client.get("/whoami")
        self.assertEqual(response.status_code, 302)
        self.assertIn("?next=/whoami", response.headers["Location"])
