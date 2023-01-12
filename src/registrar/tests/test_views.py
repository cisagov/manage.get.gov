from unittest import skip

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from django_webtest import WebTest  # type: ignore

from registrar.models import DomainApplication, Domain, Contact, Website
from registrar.views.application import ApplicationWizard, Step

from .common import less_console_noise


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
        # delete any applications too
        DomainApplication.objects.all().delete()
        self.user.delete()


class LoggedInTests(TestWithUser):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_home_lists_domain_applications(self):
        response = self.client.get("/")
        self.assertNotContains(response, "igorville.gov")
        site = Domain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=self.user, requested_domain=site
        )
        response = self.client.get("/")
        self.assertContains(response, "igorville.gov", count=1)
        # clean up
        application.delete()

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
            response,
            "What kind of U.S.-based government organization do you represent?",
        )


class DomainApplicationTests(TestWithUser, WebTest):

    """Webtests for domain application to test filling and submitting."""

    # Doesn't work with CSRF checking
    # hypothesis is that CSRF_USE_SESSIONS is incompatible with WebTest
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.TITLES = ApplicationWizard.TITLES

    def test_application_form_empty_submit(self):
        # 302 redirect to the first form
        page = self.app.get(reverse("application:")).follow()
        # submitting should get back the same page if the required field is empty
        result = page.form.submit()
        self.assertIn(
            "What kind of U.S.-based government organization do you represent?", result
        )

    def test_application_form_submission(self):
        """Can fill out the entire form and submit.
        As we add additional form pages, we need to include them here to make
        this test work.
        """
        num_pages_tested = 0
        SKIPPED_PAGES = 2  # elections, type_of_work
        num_pages = len(self.TITLES) - SKIPPED_PAGES

        type_page = self.app.get(reverse("application:")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.form
        type_form["organization_type-organization_type"] = "federal"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = type_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/organization_type/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.organization_type, "federal")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.form.submit()

        # the post request should return a redirect to the next form in
        # the application
        self.assertEquals(type_result.status_code, 302)
        self.assertEquals(type_result["Location"], "/register/organization_federal/")
        num_pages_tested += 1

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        federal_form = federal_page.form
        federal_form["organization_federal-federal_type"] = "executive"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = federal_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/organization_federal/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.federal_type, "executive")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()

        self.assertEquals(federal_result.status_code, 302)
        self.assertEquals(federal_result["Location"], "/register/organization_contact/")
        num_pages_tested += 1

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.form
        # federal agency so we have to fill in federal_agency
        org_contact_form[
            "organization_contact-federal_agency"
        ] = "General Services Administration"
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = org_contact_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/organization_contact/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.organization_name, "Testorg")
        self.assertEquals(application.address_line1, "address 1")
        self.assertEquals(application.address_line2, "address 2")
        self.assertEquals(application.city, "NYC")
        self.assertEquals(application.state_territory, "NY")
        self.assertEquals(application.zipcode, "10002")
        self.assertEquals(application.urbanization, "URB Royal Oaks")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        self.assertEquals(org_contact_result.status_code, 302)
        self.assertEquals(
            org_contact_result["Location"], "/register/authorizing_official/"
        )
        num_pages_tested += 1

        # ---- AUTHORIZING OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()
        ao_form = ao_page.form
        ao_form["authorizing_official-first_name"] = "Testy ATO"
        ao_form["authorizing_official-last_name"] = "Tester ATO"
        ao_form["authorizing_official-title"] = "Chief Tester"
        ao_form["authorizing_official-email"] = "testy@town.com"
        ao_form["authorizing_official-phone"] = "(201) 555 5555"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = ao_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/authorizing_official/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.authorizing_official.first_name, "Testy ATO")
        self.assertEquals(application.authorizing_official.last_name, "Tester ATO")
        self.assertEquals(application.authorizing_official.title, "Chief Tester")
        self.assertEquals(application.authorizing_official.email, "testy@town.com")
        self.assertEquals(application.authorizing_official.phone, "(201) 555 5555")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_result = ao_form.submit()

        self.assertEquals(ao_result.status_code, 302)
        self.assertEquals(ao_result["Location"], "/register/current_sites/")
        num_pages_tested += 1

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = ao_result.follow()
        current_sites_form = current_sites_page.form
        current_sites_form["current_sites-current_site"] = "www.city.com"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = current_sites_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/current_sites/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(
            application.current_websites.filter(website="city.com").count(), 1
        )

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()

        self.assertEquals(current_sites_result.status_code, 302)
        self.assertEquals(current_sites_result["Location"], "/register/dotgov_domain/")
        num_pages_tested += 1

        # ---- DOTGOV DOMAIN PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = current_sites_result.follow()
        dotgov_form = dotgov_page.form
        dotgov_form["dotgov_domain-requested_domain"] = "city"
        dotgov_form["dotgov_domain-alternative_domain"] = "city1"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = dotgov_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/dotgov_domain/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.requested_domain.name, "city.gov")
        self.assertEquals(
            application.alternative_domains.filter(website="city1.gov").count(), 1
        )

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_result = dotgov_form.submit()

        self.assertEquals(dotgov_result.status_code, 302)
        self.assertEquals(dotgov_result["Location"], "/register/purpose/")
        num_pages_tested += 1

        # ---- PURPOSE PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_page = dotgov_result.follow()
        purpose_form = purpose_page.form
        purpose_form["purpose-purpose"] = "For all kinds of things."

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = purpose_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/purpose/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.purpose, "For all kinds of things.")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_result = purpose_form.submit()

        self.assertEquals(purpose_result.status_code, 302)
        self.assertEquals(purpose_result["Location"], "/register/your_contact/")
        num_pages_tested += 1

        # ---- YOUR CONTACT INFO PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        your_contact_page = purpose_result.follow()
        your_contact_form = your_contact_page.form

        your_contact_form["your_contact-first_name"] = "Testy you"
        your_contact_form["your_contact-last_name"] = "Tester you"
        your_contact_form["your_contact-title"] = "Admin Tester"
        your_contact_form["your_contact-email"] = "testy-admin@town.com"
        your_contact_form["your_contact-phone"] = "(201) 555 5556"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = your_contact_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/your_contact/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.submitter.first_name, "Testy you")
        self.assertEquals(application.submitter.last_name, "Tester you")
        self.assertEquals(application.submitter.title, "Admin Tester")
        self.assertEquals(application.submitter.email, "testy-admin@town.com")
        self.assertEquals(application.submitter.phone, "(201) 555 5556")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        your_contact_result = your_contact_form.submit()

        self.assertEquals(your_contact_result.status_code, 302)
        self.assertEquals(your_contact_result["Location"], "/register/other_contacts/")
        num_pages_tested += 1

        # ---- OTHER CONTACTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_page = your_contact_result.follow()
        other_contacts_form = other_contacts_page.form

        other_contacts_form["other_contacts-first_name"] = "Testy2"
        other_contacts_form["other_contacts-last_name"] = "Tester2"
        other_contacts_form["other_contacts-title"] = "Another Tester"
        other_contacts_form["other_contacts-email"] = "testy2@town.com"
        other_contacts_form["other_contacts-phone"] = "(201) 555 5557"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = other_contacts_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/other_contacts/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(
            application.other_contacts.filter(
                first_name="Testy2",
                last_name="Tester2",
                title="Another Tester",
                email="testy2@town.com",
                phone="(201) 555 5557",
            ).count(),
            1,
        )

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_result = other_contacts_form.submit()

        self.assertEquals(other_contacts_result.status_code, 302)
        self.assertEquals(
            other_contacts_result["Location"], "/register/security_email/"
        )
        num_pages_tested += 1

        # ---- SECURITY EMAIL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        security_email_page = other_contacts_result.follow()
        security_email_form = security_email_page.form

        security_email_form["security_email-security_email"] = "security@city.com"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = security_email_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/security_email/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.security_email, "security@city.com")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        security_email_result = security_email_form.submit()

        self.assertEquals(security_email_result.status_code, 302)
        self.assertEquals(security_email_result["Location"], "/register/anything_else/")
        num_pages_tested += 1

        # ---- ANYTHING ELSE PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        anything_else_page = security_email_result.follow()
        anything_else_form = anything_else_page.form

        anything_else_form["anything_else-anything_else"] = "Nothing else."

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = anything_else_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/anything_else/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.anything_else, "Nothing else.")

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        anything_else_result = anything_else_form.submit()

        self.assertEquals(anything_else_result.status_code, 302)
        self.assertEquals(anything_else_result["Location"], "/register/requirements/")
        num_pages_tested += 1

        # ---- REQUIREMENTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_page = anything_else_result.follow()
        requirements_form = requirements_page.form

        requirements_form["requirements-is_policy_acknowledged"] = True

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = requirements_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/requirements/")
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEquals(application.is_policy_acknowledged, True)

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_result = requirements_form.submit()

        self.assertEquals(requirements_result.status_code, 302)
        self.assertEquals(requirements_result["Location"], "/register/review/")
        num_pages_tested += 1

        # ---- REVIEW AND FINSIHED PAGES  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        review_page = requirements_result.follow()
        review_form = review_page.form

        # Review page contains all the previously entered data
        self.assertContains(review_page, "Federal")
        self.assertContains(review_page, "Executive")
        self.assertContains(review_page, "Testorg")
        self.assertContains(review_page, "address 1")
        self.assertContains(review_page, "address 2")
        self.assertContains(review_page, "NYC")
        self.assertContains(review_page, "NY")
        self.assertContains(review_page, "10002")
        self.assertContains(review_page, "URB Royal Oaks")
        self.assertContains(review_page, "Testy ATO")
        self.assertContains(review_page, "Tester ATO")
        self.assertContains(review_page, "Chief Tester")
        self.assertContains(review_page, "testy@town.com")
        self.assertContains(review_page, "(201) 555-5555")
        self.assertContains(review_page, "city.com")
        self.assertContains(review_page, "city.gov")
        self.assertContains(review_page, "city1.gov")
        self.assertContains(review_page, "For all kinds of things.")
        self.assertContains(review_page, "Testy you")
        self.assertContains(review_page, "Tester you")
        self.assertContains(review_page, "Admin Tester")
        self.assertContains(review_page, "testy-admin@town.com")
        self.assertContains(review_page, "(201) 555-5556")
        self.assertContains(review_page, "Testy2")
        self.assertContains(review_page, "Tester2")
        self.assertContains(review_page, "Another Tester")
        self.assertContains(review_page, "testy2@town.com")
        self.assertContains(review_page, "(201) 555-5557")
        self.assertContains(review_page, "security@city.com")
        self.assertContains(review_page, "Nothing else.")

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        result = review_page.form.submit("submit_button", value="save")
        # should remain on the same page
        self.assertEquals(result["Location"], "/register/review/")

        # final submission results in a redirect to the "finished" URL
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        with less_console_noise():
            review_result = review_form.submit()

        self.assertEquals(review_result.status_code, 302)
        self.assertEquals(review_result["Location"], "/register/finished/")
        num_pages_tested += 1

        # following this redirect is a GET request, so include the cookie
        # here too.
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        with less_console_noise():
            final_result = review_result.follow()
        self.assertContains(final_result, "Thank you for your domain request")

        # check that any new pages are added to this test
        self.assertEqual(num_pages, num_pages_tested)

    def test_application_form_conditional_federal(self):
        """Federal branch question is shown for federal organizations."""
        type_page = self.app.get(reverse("application:")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----

        # the conditional step titles shouldn't appear initially
        self.assertNotContains(type_page, self.TITLES["organization_federal"])
        self.assertNotContains(type_page, self.TITLES["organization_election"])
        type_form = type_page.form
        type_form["organization_type-organization_type"] = "federal"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the federal branch
        # question
        self.assertEquals(type_result.status_code, 302)
        self.assertEquals(type_result["Location"], "/register/organization_federal/")

        # and the step label should appear in the sidebar of the resulting page
        # but the step label for the elections page should not appear
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        self.assertContains(federal_page, self.TITLES["organization_federal"])
        self.assertNotContains(federal_page, self.TITLES["organization_election"])

        # continuing on in the flow we need to see top-level agency on the
        # contact page
        federal_page.form["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_page.form.submit()
        # the post request should return a redirect to the contact
        # question
        self.assertEquals(federal_result.status_code, 302)
        self.assertEquals(federal_result["Location"], "/register/organization_contact/")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = federal_result.follow()
        self.assertContains(contact_page, "Federal agency")

    def test_application_form_conditional_elections(self):
        """Election question is shown for other organizations."""
        type_page = self.app.get(reverse("application:")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----

        # the conditional step titles shouldn't appear initially
        self.assertNotContains(type_page, self.TITLES["organization_federal"])
        self.assertNotContains(type_page, self.TITLES["organization_election"])
        type_form = type_page.form
        type_form["organization_type-organization_type"] = "county"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the elections question
        self.assertEquals(type_result.status_code, 302)
        self.assertEquals(type_result["Location"], "/register/organization_election/")

        # and the step label should appear in the sidebar of the resulting page
        # but the step label for the elections page should not appear
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()
        self.assertContains(election_page, self.TITLES["organization_election"])
        self.assertNotContains(election_page, self.TITLES["organization_federal"])

        # continuing on in the flow we need to NOT see top-level agency on the
        # contact page
        election_page.form["organization_election-is_election_board"] = "True"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_result = election_page.form.submit()
        # the post request should return a redirect to the contact
        # question
        self.assertEquals(election_result.status_code, 302)
        self.assertEquals(
            election_result["Location"], "/register/organization_contact/"
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = election_result.follow()
        self.assertNotContains(contact_page, "Federal agency")

    def test_application_form_section_skipping(self):
        """Can skip forward and back in sections"""
        type_page = self.app.get(reverse("application:")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.form
        type_form["organization_type-organization_type"] = "federal"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()

        # Now on federal type page, click back to the organization type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        new_page = federal_page.click(str(self.TITLES["organization_type"]), index=0)

        # Should be a link to the organization_federal page
        self.assertGreater(
            len(new_page.html.find_all("a", href="/register/organization_federal/")),
            0,
        )

    def test_application_form_nonfederal(self):
        """Non-federal organizations don't have to provide their federal agency."""
        type_page = self.app.get(reverse("application:")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.form
        type_form[
            "organization_type-organization_type"
        ] = DomainApplication.OrganizationChoices.INTERSTATE
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()
        org_contact_form = contact_page.form

        self.assertNotIn("federal_agency", org_contact_form.fields)

        # minimal fields that must be filled out
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_result = org_contact_form.submit()

        # the post request should return a redirect to the type of work page
        # if it was successful.
        self.assertEquals(contact_result.status_code, 302)
        self.assertEquals(contact_result["Location"], "/register/type_of_work/")

    def test_application_type_of_work_special(self):
        """Special districts have to answer an additional question."""
        type_page = self.app.get(reverse("application:")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.form
        type_form[
            "organization_type-organization_type"
        ] = DomainApplication.OrganizationChoices.SPECIAL_DISTRICT
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.form.submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.TYPE_OF_WORK])

    def test_application_type_of_work_interstate(self):
        """Special districts have to answer an additional question."""
        type_page = self.app.get(reverse("application:")).follow()
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.form
        type_form[
            "organization_type-organization_type"
        ] = DomainApplication.OrganizationChoices.INTERSTATE
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.form.submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.TYPE_OF_WORK])

    @skip("WIP")
    def test_application_edit_restore(self):
        """
        Test that a previously saved application is available at the /edit endpoint.
        """
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(555) 555 5555",
        )
        domain, _ = Domain.objects.get_or_create(name="city.gov")
        alt, _ = Website.objects.get_or_create(website="city1.gov")
        current, _ = Website.objects.get_or_create(website="city.com")
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(555) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(555) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            security_email="security@city.com",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            requested_domain=domain,
            submitter=you,
            creator=self.user,
        )
        application.other_contacts.add(other)
        application.current_websites.add(current)
        application.alternative_domains.add(alt)

        # prime the form by visiting /edit
        url = reverse("edit-application", kwargs={"id": application.pk})
        response = self.client.get(url)

        # TODO: this is a sketch of each page in the wizard which needs to be tested
        # Django does not have tools sufficient for real end to end integration testing
        # (for example, USWDS moves radio buttons off screen and replaces them with
        # CSS styled "fakes" -- Django cannot determine if those are visually correct)
        # -- the best that can/should be done here is to ensure the correct values
        # are being passed to the templating engine

        url = reverse("application:organization_type")
        response = self.client.get(url, follow=True)
        self.assertContains(response, "<input>")
        # choices = response.context['wizard']['form']['organization_type'].subwidgets
        # radio = [ x for x in choices if x.data["value"] == "federal" ][0]
        # checked = radio.data["selected"]
        # self.assertTrue(checked)

        # url = reverse("application:organization_federal")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:organization_contact")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:authorizing_official")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:current_sites")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:dotgov_domain")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:purpose")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:your_contact")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:other_contacts")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:other_contacts")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:security_email")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:anything_else")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:requirements")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")
