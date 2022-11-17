from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from django_webtest import WebTest  # type: ignore


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

    def test_whoami_page_no_user(self):
        """Whoami page not accessible without a logged-in user."""
        response = self.client.get("/whoami/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("?next=/whoami/", response.headers["Location"])

    def test_application_form_not_logged_in(self):
        """Application form not accessible without a logged-in user."""
        response = self.client.get("/register/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=/register/", response.headers["Location"])


class TestWithUser(TestCase):
    def setUp(self):
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )

    def tearDown(self):
        self.user.delete()


class LoggedInTests(TestWithUser):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_whoami_page(self):
        """User information appears on the whoami page."""
        response = self.client.get("/whoami/")
        self.assertContains(response, self.user.first_name)
        self.assertContains(response, self.user.last_name)
        self.assertContains(response, self.user.email)

    def test_edit_profile(self):
        response = self.client.get("/edit_profile/")
        self.assertContains(response, "Display Name")

    def test_application_form_view(self):
        response = self.client.get("/register/", follow=True)
        self.assertContains(
            response, "What kind of government organization do you represent?"
        )


class FormTests(TestWithUser, WebTest):

    """Webtests for forms to test filling and submitting."""

    # Doesn't work with CSRF checking
    # hypothesis is that CSRF_USE_SESSIONS is incompatible with WebTest
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)

    def test_application_form_empty_submit(self):
        # 302 redirect to the first form
        page = self.app.get(reverse("application")).follow()
        # submitting should get back the same page if the required field is empty
        result = page.form.submit()
        self.assertIn("What kind of government organization do you represent?", result)

    def test_application_form_organization(self):
        # 302 redirect to the first form
        page = self.app.get(reverse("application")).follow()
        form = page.form
        form["organization_type-organization_type"] = "Federal"
        result = page.form.submit().follow()
        # Got the next form page
        self.assertIn("contact information", result)
