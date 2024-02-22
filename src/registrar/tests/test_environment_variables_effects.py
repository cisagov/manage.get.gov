from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model


class MyTestCase(TestCase):
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
