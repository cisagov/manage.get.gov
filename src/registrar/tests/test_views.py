from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from django_webtest import WebTest  # type: ignore

from registrar.models import DomainApplication


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
        self.assertContains(response, "About your organization")


class FormTests(TestWithUser, WebTest):

    """Webtests for forms to test filling and submitting."""

    # Doesn't work with CSRF checking
    # hypothesis is that CSRF_USE_SESSIONS is incompatible with WebTest
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)

    def tearDown(self):
        # delete any applications we made so that users can be deleted\
        DomainApplication.objects.all().delete()
        super().tearDown()

    def test_application_form_empty_submit(self):
        # 302 redirect to the first form
        page = self.app.get(reverse("application")).follow()
        # submitting should get back the same page if the required field is empty
        result = page.form.submit()
        self.assertIn("About your organization", result)

    def test_application_form_organization(self):
        # 302 redirect to the first form
        page = self.app.get(reverse("application")).follow()
        form = page.form
        form["organization-organization_type"] = "Federal"
        result = page.form.submit().follow()
        # Got the next form page
        self.assertContains(result, "contact information")

    def test_application_form_submission(self):
        """Can fill out the entire form and submit.

        As we add additional form pages, we need to include them here to make
        this test work.
        """
        page = self.app.get(reverse("application")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        form = page.form
        form["organization-organization_type"] = "Federal"
        form["organization-federal_type"] = "Executive"
        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = page.form.submit()

        # the post request should return a redirect to the next form in
        # the application
        self.assertEquals(result.status_code, 302)
        self.assertEquals(result["Location"], "/register/contact/")

        # Follow the redirect to the next form page
        next_page = result.follow()
        contact_form = next_page.form
        contact_form["contact-organization_name"] = "test"
        contact_form["contact-street_address"] = "100 Main Street"
        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = contact_form.submit()

        # final submission results in a redirect to the "finished" URL
        self.assertEquals(result.status_code, 302)
        self.assertEquals(result["Location"], "/register/finished/")

        # the finished URL (for now) returns a redirect to /
        # following this redirect is a GET request, so include the cookie
        # here too.
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        next_result = result.follow()
        self.assertContains(next_result, "Thank you for your domain request")
