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

    def tearDown(self):
        # delete any applications we made so that users can be deleted\
        DomainApplication.objects.all().delete()
        super().tearDown()

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
        self.assertContains(result, "contact information")

    def test_application_form_submission(self):
        """Can fill out the entire form and submit.
        As we add additional form pages, we need to include them here to make
        this test work.
        """
        type_page = self.app.get(reverse("application")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.form
        type_form["organization_type-organization_type"] = "Federal"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.form.submit()

        # the post request should return a redirect to the next form in
        # the application
        self.assertEquals(type_result.status_code, 302)
        self.assertEquals(type_result["Location"], "/register/organization_federal/")

        # TODO: In the future this should be conditionally dispalyed based on org type

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        federal_page = type_result.follow()
        federal_form = federal_page.form
        federal_form["organization_federal-federal_type"] = "Executive"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()

        self.assertEquals(federal_result.status_code, 302)
        self.assertEquals(
            federal_result["Location"], "/register/organization_election/"
        )

        # ---- ELECTION BOARD BRANCH PAGE  ----
        # Follow the redirect to the next form page
        election_page = federal_result.follow()
        election_form = election_page.form
        election_form["organization_election-is_election_board"] = True

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_result = election_form.submit()

        self.assertEquals(election_result.status_code, 302)
        self.assertEquals(
            election_result["Location"], "/register/organization_contact/"
        )

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        org_contact_page = election_result.follow()
        org_contact_form = org_contact_page.form
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-us_state"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        self.assertEquals(org_contact_result.status_code, 302)
        self.assertEquals(
            org_contact_result["Location"], "/register/authorizing_official/"
        )
        # ---- AUTHORIZING OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        ao_page = org_contact_result.follow()
        ao_form = ao_page.form
        ao_form["authorizing_official-first_name"] = "Testy"
        ao_form["authorizing_official-last_name"] = "Tester"
        ao_form["authorizing_official-title"] = "Chief Tester"
        ao_form["authorizing_official-email"] = "testy@town.com"
        ao_form["authorizing_official-phone"] = "(555) 555 5555"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_result = ao_form.submit()

        self.assertEquals(ao_result.status_code, 302)
        self.assertEquals(ao_result["Location"], "/register/current_sites/")

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        current_sites_page = ao_result.follow()
        current_sites_form = current_sites_page.form
        current_sites_form["current_sites-current_site"] = "www.city.com"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()

        self.assertEquals(current_sites_result.status_code, 302)
        self.assertEquals(current_sites_result["Location"], "/register/dotgov_domain/")

        # ---- DOTGOV DOMAIN PAGE  ----
        # Follow the redirect to the next form page
        dotgov_page = current_sites_result.follow()
        dotgov_form = dotgov_page.form
        dotgov_form["dotgov_domain-dotgov_domain"] = "city"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_result = dotgov_form.submit()

        self.assertEquals(dotgov_result.status_code, 302)
        self.assertEquals(dotgov_result["Location"], "/register/purpose/")

        # ---- PURPOSE DOMAIN PAGE  ----
        # Follow the redirect to the next form page
        purpose_page = dotgov_result.follow()
        purpose_form = purpose_page.form
        purpose_form["purpose-purpose_field"] = "Purpose of the site"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_result = purpose_form.submit()

        self.assertEquals(purpose_result.status_code, 302)
        self.assertEquals(purpose_result["Location"], "/register/your_contact/")

        # ---- YOUR CONTACT INFO PAGE  ----
        # Follow the redirect to the next form page
        your_contact_page = purpose_result.follow()
        your_contact_form = your_contact_page.form

        your_contact_form["your_contact-first_name"] = "Testy you"
        your_contact_form["your_contact-last_name"] = "Tester you"
        your_contact_form["your_contact-title"] = "Admin Tester"
        your_contact_form["your_contact-email"] = "testy-admin@town.com"
        your_contact_form["your_contact-phone"] = "(555) 555 5556"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        your_contact_result = your_contact_form.submit()

        self.assertEquals(your_contact_result.status_code, 302)
        self.assertEquals(your_contact_result["Location"], "/register/other_contacts/")

        # ---- OTHER CONTACTS PAGE  ----
        # Follow the redirect to the next form page
        other_contacts_page = your_contact_result.follow()
        other_contacts_form = other_contacts_page.form

        other_contacts_form["other_contacts-first_name"] = "Testy2"
        other_contacts_form["other_contacts-last_name"] = "Tester2"
        other_contacts_form["other_contacts-title"] = "Another Tester"
        other_contacts_form["other_contacts-email"] = "testy2@town.com"
        other_contacts_form["other_contacts-phone"] = "(555) 555 5557"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_result = other_contacts_form.submit()

        self.assertEquals(other_contacts_result.status_code, 302)
        self.assertEquals(
            other_contacts_result["Location"], "/register/security_email/"
        )

        # ---- SECURITY EMAIL PAGE  ----
        # Follow the redirect to the next form page
        security_email_page = other_contacts_result.follow()
        security_email_form = security_email_page.form

        security_email_form["security_email-email"] = "security@city.com"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        security_email_result = security_email_form.submit()

        self.assertEquals(security_email_result.status_code, 302)
        self.assertEquals(security_email_result["Location"], "/register/anything_else/")

        # ---- ANYTHING ELSE PAGE  ----
        # Follow the redirect to the next form page
        anything_else_page = security_email_result.follow()
        anything_else_form = anything_else_page.form

        anything_else_form["anything_else-anything_else"] = "No"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        anything_else_result = anything_else_form.submit()

        self.assertEquals(anything_else_result.status_code, 302)
        self.assertEquals(anything_else_result["Location"], "/register/requirements/")

        # ---- REQUIREMENTS PAGE  ----
        # Follow the redirect to the next form page
        requirements_page = anything_else_result.follow()
        requirements_form = requirements_page.form

        requirements_form["requirements-agree_check"] = True

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_result = requirements_form.submit()

        self.assertEquals(requirements_result.status_code, 302)
        self.assertEquals(requirements_result["Location"], "/register/review/")

        # ---- REVIEW AND FINSIHED PAGES  ----
        # Follow the redirect to the next form page
        review_page = requirements_result.follow()
        review_form = review_page.form

        # final submission results in a redirect to the "finished" URL

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        review_result = review_form.submit()

        self.assertEquals(review_result.status_code, 302)
        self.assertEquals(review_result["Location"], "/register/finished/")

        # following this redirect is a GET request, so include the cookie
        # here too.
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        final_result = review_result.follow()
        self.assertContains(final_result, "Thank you for your domain request")
