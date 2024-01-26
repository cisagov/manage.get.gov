from unittest import skip
from unittest.mock import MagicMock, ANY, patch

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .common import MockEppLib, MockSESClient, completed_application, create_user  # type: ignore
from django_webtest import WebTest  # type: ignore
import boto3_mocking  # type: ignore

from registrar.utility.errors import (
    NameserverError,
    NameserverErrorCodes,
    SecurityEmailError,
    SecurityEmailErrorCodes,
    GenericError,
    GenericErrorCodes,
    DsDataError,
    DsDataErrorCodes,
)

from registrar.models import (
    DomainApplication,
    Domain,
    DomainInformation,
    DraftDomain,
    DomainInvitation,
    Contact,
    PublicContact,
    Host,
    HostIP,
    Website,
    UserDomainRole,
    User,
)
from registrar.views.application import ApplicationWizard, Step
from datetime import date, datetime, timedelta
from django.utils import timezone

from .common import less_console_noise
import logging

logger = logging.getLogger(__name__)


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        response = self.client.get("/health/")
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
        DomainApplication.objects.all().delete()
        DomainInformation.objects.all().delete()
        self.user.delete()


class LoggedInTests(TestWithUser):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        Contact.objects.all().delete()

    def test_home_lists_domain_applications(self):
        response = self.client.get("/")
        self.assertNotContains(response, "igorville.gov")
        site = DraftDomain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(creator=self.user, requested_domain=site)
        response = self.client.get("/")

        # count = 7 because of screenreader content
        self.assertContains(response, "igorville.gov", count=7)

        # clean up
        application.delete()

    def test_home_deletes_withdrawn_domain_application(self):
        """Tests if the user can delete a DomainApplication in the 'withdrawn' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=self.user, requested_domain=site, status=DomainApplication.ApplicationStatus.WITHDRAWN
        )

        # Ensure that igorville.gov exists on the page
        home_page = self.client.get("/")
        self.assertContains(home_page, "igorville.gov")

        # Check if the delete button exists. We can do this by checking for its id and text content.
        self.assertContains(home_page, "Delete")
        self.assertContains(home_page, "button-toggle-delete-domain-alert-1")

        # Trigger the delete logic
        response = self.client.post(reverse("application-delete", kwargs={"pk": application.pk}), follow=True)

        self.assertNotContains(response, "igorville.gov")

        # clean up
        application.delete()

    def test_home_deletes_started_domain_application(self):
        """Tests if the user can delete a DomainApplication in the 'started' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=self.user, requested_domain=site, status=DomainApplication.ApplicationStatus.STARTED
        )

        # Ensure that igorville.gov exists on the page
        home_page = self.client.get("/")
        self.assertContains(home_page, "igorville.gov")

        # Check if the delete button exists. We can do this by checking for its id and text content.
        self.assertContains(home_page, "Delete")
        self.assertContains(home_page, "button-toggle-delete-domain-alert-1")

        # Trigger the delete logic
        response = self.client.post(reverse("application-delete", kwargs={"pk": application.pk}), follow=True)

        self.assertNotContains(response, "igorville.gov")

        # clean up
        application.delete()

    def test_home_doesnt_delete_other_domain_applications(self):
        """Tests to ensure the user can't delete Applications not in the status of STARTED or WITHDRAWN"""

        # Given that we are including a subset of items that can be deleted while excluding the rest,
        # subTest is appropriate here as otherwise we would need many duplicate tests for the same reason.
        draft_domain = DraftDomain.objects.create(name="igorville.gov")
        for status in DomainApplication.ApplicationStatus:
            if status not in [
                DomainApplication.ApplicationStatus.STARTED,
                DomainApplication.ApplicationStatus.WITHDRAWN,
            ]:
                with self.subTest(status=status):
                    application = DomainApplication.objects.create(
                        creator=self.user, requested_domain=draft_domain, status=status
                    )

                    # Trigger the delete logic
                    response = self.client.post(
                        reverse("application-delete", kwargs={"pk": application.pk}), follow=True
                    )

                    # Check for a 403 error - the end user should not be allowed to do this
                    self.assertEqual(response.status_code, 403)

                    desired_application = DomainApplication.objects.filter(requested_domain=draft_domain)

                    # Make sure the DomainApplication wasn't deleted
                    self.assertEqual(desired_application.count(), 1)

                    # clean up
                    application.delete()

    def test_home_deletes_domain_application_and_orphans(self):
        """Tests if delete for DomainApplication deletes orphaned Contact objects"""

        # Create the site and contacts to delete (orphaned)
        contact = Contact.objects.create(
            first_name="Henry",
            last_name="Mcfakerson",
        )
        contact_shared = Contact.objects.create(
            first_name="Relative",
            last_name="Aether",
        )

        # Create two non-orphaned contacts
        contact_2 = Contact.objects.create(
            first_name="Saturn",
            last_name="Mars",
        )

        # Attach a user object to a contact (should not be deleted)
        contact_user, _ = Contact.objects.get_or_create(user=self.user)

        site = DraftDomain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainApplication.ApplicationStatus.WITHDRAWN,
            authorizing_official=contact,
            submitter=contact_user,
        )
        application.other_contacts.set([contact_2])

        # Create a second application to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        application_2 = DomainApplication.objects.create(
            creator=self.user,
            requested_domain=site_2,
            status=DomainApplication.ApplicationStatus.STARTED,
            authorizing_official=contact_2,
            submitter=contact_shared,
        )
        application_2.other_contacts.set([contact_shared])

        # Ensure that igorville.gov exists on the page
        home_page = self.client.get("/")
        self.assertContains(home_page, "igorville.gov")

        # Trigger the delete logic
        response = self.client.post(reverse("application-delete", kwargs={"pk": application.pk}), follow=True)

        # igorville is now deleted
        self.assertNotContains(response, "igorville.gov")

        # Check if the orphaned contact was deleted
        orphan = Contact.objects.filter(id=contact.id)
        self.assertFalse(orphan.exists())

        # All non-orphan contacts should still exist and are unaltered
        try:
            current_user = Contact.objects.filter(id=contact_user.id).get()
        except Contact.DoesNotExist:
            self.fail("contact_user (a non-orphaned contact) was deleted")

        self.assertEqual(current_user, contact_user)
        try:
            edge_case = Contact.objects.filter(id=contact_2.id).get()
        except Contact.DoesNotExist:
            self.fail("contact_2 (a non-orphaned contact) was deleted")

        self.assertEqual(edge_case, contact_2)

    def test_home_deletes_domain_application_and_shared_orphans(self):
        """Test the edge case for an object that will become orphaned after a delete
        (but is not an orphan at the time of deletion)"""

        # Create the site and contacts to delete (orphaned)
        contact = Contact.objects.create(
            first_name="Henry",
            last_name="Mcfakerson",
        )
        contact_shared = Contact.objects.create(
            first_name="Relative",
            last_name="Aether",
        )

        # Create two non-orphaned contacts
        contact_2 = Contact.objects.create(
            first_name="Saturn",
            last_name="Mars",
        )

        # Attach a user object to a contact (should not be deleted)
        contact_user, _ = Contact.objects.get_or_create(user=self.user)

        site = DraftDomain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainApplication.ApplicationStatus.WITHDRAWN,
            authorizing_official=contact,
            submitter=contact_user,
        )
        application.other_contacts.set([contact_2])

        # Create a second application to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        application_2 = DomainApplication.objects.create(
            creator=self.user,
            requested_domain=site_2,
            status=DomainApplication.ApplicationStatus.STARTED,
            authorizing_official=contact_2,
            submitter=contact_shared,
        )
        application_2.other_contacts.set([contact_shared])

        home_page = self.client.get("/")
        self.assertContains(home_page, "teaville.gov")

        # Trigger the delete logic
        response = self.client.post(reverse("application-delete", kwargs={"pk": application_2.pk}), follow=True)

        self.assertNotContains(response, "teaville.gov")

        # Check if the orphaned contact was deleted
        orphan = Contact.objects.filter(id=contact_shared.id)
        self.assertFalse(orphan.exists())

    def test_application_form_view(self):
        response = self.client.get("/request/", follow=True)
        self.assertContains(
            response,
            "You’re about to start your .gov domain request.",
        )

    def test_domain_application_form_with_ineligible_user(self):
        """Application form not accessible for an ineligible user.
        This test should be solid enough since all application wizard
        views share the same permissions class"""
        self.user.status = User.RESTRICTED
        self.user.save()

        with less_console_noise():
            response = self.client.get("/request/", follow=True)
            print(response.status_code)
            self.assertEqual(response.status_code, 403)


class DomainApplicationTests(TestWithUser, WebTest):

    """Webtests for domain application to test filling and submitting."""

    # Doesn't work with CSRF checking
    # hypothesis is that CSRF_USE_SESSIONS is incompatible with WebTest
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.TITLES = ApplicationWizard.TITLES

    def test_application_form_intro_acknowledgement(self):
        """Tests that user is presented with intro acknowledgement page"""
        intro_page = self.app.get(reverse("application:"))
        self.assertContains(intro_page, "You’re about to start your .gov domain request")

    def test_application_form_intro_is_skipped_when_edit_access(self):
        """Tests that user is NOT presented with intro acknowledgement page when accessed through 'edit'"""
        completed_application(status=DomainApplication.ApplicationStatus.STARTED, user=self.user)
        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Edit" link
        detail_page = home_page.click("Edit", index=0)
        # Check that the response is a redirect
        self.assertEqual(detail_page.status_code, 302)
        # You can access the 'Location' header to get the redirect URL
        redirect_url = detail_page.url
        self.assertEqual(redirect_url, "/request/organization_type/")

    def test_application_form_empty_submit(self):
        """Tests empty submit on the first page after the acknowledgement page"""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # submitting should get back the same page if the required field is empty
        result = type_page.forms[0].submit()
        self.assertIn("What kind of U.S.-based government organization do you represent?", result)

    def test_application_multiple_applications_exist(self):
        """Test that an info message appears when user has multiple applications already"""
        # create and submit an application
        application = completed_application(user=self.user)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                application.submit()
                application.save()

        # now, attempt to create another one
        with less_console_noise():
            intro_page = self.app.get(reverse("application:"))
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            intro_form = intro_page.forms[0]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            intro_result = intro_form.submit()

            # follow first redirect
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            type_page = intro_result.follow()
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

            self.assertContains(type_page, "You cannot submit this request yet")

    @boto3_mocking.patching
    def test_application_form_submission(self):
        """
        Can fill out the entire form and submit.
        As we add additional form pages, we need to include them here to make
        this test work.

        This test also looks for the long organization name on the summary page.

        This also tests for the presence of a modal trigger and the dynamic test
        in the modal header on the submit page.
        """
        num_pages_tested = 0
        # elections, type_of_work, tribal_government
        SKIPPED_PAGES = 3
        num_pages = len(self.TITLES) - SKIPPED_PAGES

        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"
        # test next button and validate data
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.organization_type, "federal")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], "/request/organization_federal/")
        num_pages_tested += 1

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        federal_page = type_result.follow()
        federal_form = federal_page.forms[0]
        federal_form["organization_federal-federal_type"] = "executive"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.federal_type, "executive")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(federal_result.status_code, 302)
        self.assertEqual(federal_result["Location"], "/request/organization_contact/")
        num_pages_tested += 1

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        # federal agency so we have to fill in federal_agency
        org_contact_form["organization_contact-federal_agency"] = "General Services Administration"
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.organization_name, "Testorg")
        self.assertEqual(application.address_line1, "address 1")
        self.assertEqual(application.address_line2, "address 2")
        self.assertEqual(application.city, "NYC")
        self.assertEqual(application.state_territory, "NY")
        self.assertEqual(application.zipcode, "10002")
        self.assertEqual(application.urbanization, "URB Royal Oaks")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(org_contact_result.status_code, 302)
        self.assertEqual(org_contact_result["Location"], "/request/authorizing_official/")
        num_pages_tested += 1

        # ---- AUTHORIZING OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()
        ao_form = ao_page.forms[0]
        ao_form["authorizing_official-first_name"] = "Testy ATO"
        ao_form["authorizing_official-last_name"] = "Tester ATO"
        ao_form["authorizing_official-title"] = "Chief Tester"
        ao_form["authorizing_official-email"] = "testy@town.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_result = ao_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.authorizing_official.first_name, "Testy ATO")
        self.assertEqual(application.authorizing_official.last_name, "Tester ATO")
        self.assertEqual(application.authorizing_official.title, "Chief Tester")
        self.assertEqual(application.authorizing_official.email, "testy@town.com")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(ao_result.status_code, 302)
        self.assertEqual(ao_result["Location"], "/request/current_sites/")
        num_pages_tested += 1

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = ao_result.follow()
        current_sites_form = current_sites_page.forms[0]
        current_sites_form["current_sites-0-website"] = "www.city.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(
            application.current_websites.filter(website="http://www.city.com").count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(current_sites_result.status_code, 302)
        self.assertEqual(current_sites_result["Location"], "/request/dotgov_domain/")
        num_pages_tested += 1

        # ---- DOTGOV DOMAIN PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = current_sites_result.follow()
        dotgov_form = dotgov_page.forms[0]
        dotgov_form["dotgov_domain-requested_domain"] = "city"
        dotgov_form["dotgov_domain-0-alternative_domain"] = "city1"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_result = dotgov_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.requested_domain.name, "city.gov")
        self.assertEqual(application.alternative_domains.filter(website="city1.gov").count(), 1)
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(dotgov_result.status_code, 302)
        self.assertEqual(dotgov_result["Location"], "/request/purpose/")
        num_pages_tested += 1

        # ---- PURPOSE PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_page = dotgov_result.follow()
        purpose_form = purpose_page.forms[0]
        purpose_form["purpose-purpose"] = "For all kinds of things."

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_result = purpose_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.purpose, "For all kinds of things.")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(purpose_result.status_code, 302)
        self.assertEqual(purpose_result["Location"], "/request/your_contact/")
        num_pages_tested += 1

        # ---- YOUR CONTACT INFO PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        your_contact_page = purpose_result.follow()
        your_contact_form = your_contact_page.forms[0]

        your_contact_form["your_contact-first_name"] = "Testy you"
        your_contact_form["your_contact-last_name"] = "Tester you"
        your_contact_form["your_contact-title"] = "Admin Tester"
        your_contact_form["your_contact-email"] = "testy-admin@town.com"
        your_contact_form["your_contact-phone"] = "(201) 555 5556"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        your_contact_result = your_contact_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.submitter.first_name, "Testy you")
        self.assertEqual(application.submitter.last_name, "Tester you")
        self.assertEqual(application.submitter.title, "Admin Tester")
        self.assertEqual(application.submitter.email, "testy-admin@town.com")
        self.assertEqual(application.submitter.phone, "(201) 555 5556")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(your_contact_result.status_code, 302)
        self.assertEqual(your_contact_result["Location"], "/request/other_contacts/")
        num_pages_tested += 1

        # ---- OTHER CONTACTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_page = your_contact_result.follow()

        # This page has 3 forms in 1.
        # Let's set the yes/no radios to enable the other contacts fieldsets
        other_contacts_form = other_contacts_page.forms[0]

        other_contacts_form["other_contacts-has_other_contacts"] = "True"

        other_contacts_form["other_contacts-0-first_name"] = "Testy2"
        other_contacts_form["other_contacts-0-last_name"] = "Tester2"
        other_contacts_form["other_contacts-0-title"] = "Another Tester"
        other_contacts_form["other_contacts-0-email"] = "testy2@town.com"
        other_contacts_form["other_contacts-0-phone"] = "(201) 555 5557"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_result = other_contacts_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(
            application.other_contacts.filter(
                first_name="Testy2",
                last_name="Tester2",
                title="Another Tester",
                email="testy2@town.com",
                phone="(201) 555 5557",
            ).count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(other_contacts_result.status_code, 302)
        self.assertEqual(other_contacts_result["Location"], "/request/anything_else/")
        num_pages_tested += 1

        # ---- ANYTHING ELSE PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        anything_else_page = other_contacts_result.follow()
        anything_else_form = anything_else_page.forms[0]

        anything_else_form["anything_else-anything_else"] = "Nothing else."

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        anything_else_result = anything_else_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.anything_else, "Nothing else.")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(anything_else_result.status_code, 302)
        self.assertEqual(anything_else_result["Location"], "/request/requirements/")
        num_pages_tested += 1

        # ---- REQUIREMENTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_page = anything_else_result.follow()
        requirements_form = requirements_page.forms[0]

        requirements_form["requirements-is_policy_acknowledged"] = True

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_result = requirements_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.is_policy_acknowledged, True)
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(requirements_result.status_code, 302)
        self.assertEqual(requirements_result["Location"], "/request/review/")
        num_pages_tested += 1

        # ---- REVIEW AND FINSIHED PAGES  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        review_page = requirements_result.follow()
        review_form = review_page.forms[0]

        # Review page contains all the previously entered data
        # Let's make sure the long org name is displayed
        self.assertContains(review_page, "Federal: an agency of the U.S. government")
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
        self.assertContains(review_page, "Nothing else.")

        # We can't test the modal itself as it relies on JS for init and triggering,
        # but we can test for the existence of its trigger:
        self.assertContains(review_page, "toggle-submit-domain-request")
        # And the existence of the modal's data parked and ready for the js init.
        # The next assert also tests for the passed requested domain context from
        # the view > application_form > modal
        self.assertContains(review_page, "You are about to submit a domain request for city.gov")

        # final submission results in a redirect to the "finished" URL
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        with less_console_noise():
            review_result = review_form.submit()

        self.assertEqual(review_result.status_code, 302)
        self.assertEqual(review_result["Location"], "/request/finished/")
        num_pages_tested += 1

        # following this redirect is a GET request, so include the cookie
        # here too.
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        with less_console_noise():
            final_result = review_result.follow()
        self.assertContains(final_result, "Thanks for your domain request!")

        # check that any new pages are added to this test
        self.assertEqual(num_pages, num_pages_tested)

    # This is the start of a test to check an existing application, it currently
    # does not work and results in errors as noted in:
    # https://github.com/cisagov/getgov/pull/728
    @skip("WIP")
    def test_application_form_started_allsteps(self):
        num_pages_tested = 0
        # elections, type_of_work, tribal_government
        SKIPPED_PAGES = 3
        DASHBOARD_PAGE = 1
        num_pages = len(self.TITLES) - SKIPPED_PAGES + DASHBOARD_PAGE

        application = completed_application(user=self.user)
        application.save()
        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        self.assertContains(home_page, "Started")
        num_pages_tested += 1

        # TODO: For some reason this click results in a new application being generated
        # This appraoch is an alternatie to using get as is being done below
        #
        # type_page = home_page.click("Edit")

        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        url = reverse("edit-application", kwargs={"id": application.pk})
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # TODO: The following line results in a django error on middleware
        response = self.client.get(url, follow=True)
        self.assertContains(response, "Type of organization")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # TODO: Step through the remaining pages

        self.assertEqual(num_pages, num_pages_tested)

    def test_application_form_conditional_federal(self):
        """Federal branch question is shown for federal organizations."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----

        # the conditional step titles shouldn't appear initially
        self.assertNotContains(type_page, self.TITLES["organization_federal"])
        self.assertNotContains(type_page, self.TITLES["organization_election"])
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the federal branch
        # question
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], "/request/organization_federal/")

        # and the step label should appear in the sidebar of the resulting page
        # but the step label for the elections page should not appear
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        self.assertContains(federal_page, self.TITLES["organization_federal"])
        self.assertNotContains(federal_page, self.TITLES["organization_election"])

        # continuing on in the flow we need to see top-level agency on the
        # contact page
        federal_page.forms[0]["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_page.forms[0].submit()
        # the post request should return a redirect to the contact
        # question
        self.assertEqual(federal_result.status_code, 302)
        self.assertEqual(federal_result["Location"], "/request/organization_contact/")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = federal_result.follow()
        self.assertContains(contact_page, "Federal agency")

    def test_application_form_conditional_elections(self):
        """Election question is shown for other organizations."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----

        # the conditional step titles shouldn't appear initially
        self.assertNotContains(type_page, self.TITLES["organization_federal"])
        self.assertNotContains(type_page, self.TITLES["organization_election"])
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "county"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the elections question
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], "/request/organization_election/")

        # and the step label should appear in the sidebar of the resulting page
        # but the step label for the elections page should not appear
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()
        self.assertContains(election_page, self.TITLES["organization_election"])
        self.assertNotContains(election_page, self.TITLES["organization_federal"])

        # continuing on in the flow we need to NOT see top-level agency on the
        # contact page
        election_page.forms[0]["organization_election-is_election_board"] = "True"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_result = election_page.forms[0].submit()
        # the post request should return a redirect to the contact
        # question
        self.assertEqual(election_result.status_code, 302)
        self.assertEqual(election_result["Location"], "/request/organization_contact/")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = election_result.follow()
        self.assertNotContains(contact_page, "Federal agency")

    def test_application_form_section_skipping(self):
        """Can skip forward and back in sections"""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()

        # Now on federal type page, click back to the organization type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        new_page = federal_page.click(str(self.TITLES["organization_type"]), index=0)

        # Should be a link to the organization_federal page
        self.assertGreater(
            len(new_page.html.find_all("a", href="/request/organization_federal/")),
            0,
        )

    def test_application_form_nonfederal(self):
        """Non-federal organizations don't have to provide their federal agency."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.INTERSTATE
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()
        org_contact_form = contact_page.forms[0]

        self.assertNotIn("federal_agency", org_contact_form.fields)

        # minimal fields that must be filled out
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_result = org_contact_form.submit()

        # the post request should return a redirect to the
        # about your organization page if it was successful.
        self.assertEqual(contact_result.status_code, 302)
        self.assertEqual(contact_result["Location"], "/request/about_your_organization/")

    def test_application_about_your_organization_special(self):
        """Special districts have to answer an additional question."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.SPECIAL_DISTRICT
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.forms[0].submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.ABOUT_YOUR_ORGANIZATION])

    def test_yes_no_form_inits_blank_for_new_application(self):
        """On the Other Contacts page, the yes/no form gets initialized with nothing selected for
        new applications"""
        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, None)

    def test_yes_no_form_inits_yes_for_application_with_other_contacts(self):
        """On the Other Contacts page, the yes/no form gets initialized with YES selected if the
        application has other contacts"""
        # Application has other contacts by default
        application = completed_application(user=self.user)
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

    def test_yes_no_form_inits_no_for_application_with_no_other_contacts_rationale(self):
        """On the Other Contacts page, the yes/no form gets initialized with NO selected if the
        application has no other contacts"""
        # Application has other contacts by default
        application = completed_application(user=self.user, has_other_contacts=False)
        application.no_other_contacts_rationale = "Hello!"
        application.save()
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "False")

    def test_submitting_other_contacts_deletes_no_other_contacts_rationale(self):
        """When a user submits the Other Contacts form with other contacts selected, the application's
        no other contacts rationale gets deleted"""
        # Application has other contacts by default
        application = completed_application(user=self.user, has_other_contacts=False)
        application.no_other_contacts_rationale = "Hello!"
        application.save()
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "False")

        other_contacts_form["other_contacts-has_other_contacts"] = "True"

        other_contacts_form["other_contacts-0-first_name"] = "Testy"
        other_contacts_form["other_contacts-0-middle_name"] = ""
        other_contacts_form["other_contacts-0-last_name"] = "McTesterson"
        other_contacts_form["other_contacts-0-title"] = "Lord"
        other_contacts_form["other_contacts-0-email"] = "testy@abc.org"
        other_contacts_form["other_contacts-0-phone"] = "(201) 555-0123"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier has been removed from the database
        application = DomainApplication.objects.get()
        self.assertEqual(
            application.other_contacts.count(),
            1,
        )

        self.assertEquals(
            application.no_other_contacts_rationale,
            None,
        )

    def test_submitting_no_other_contacts_rationale_deletes_other_contacts(self):
        """When a user submits the Other Contacts form with no other contacts selected, the application's
        other contacts get deleted for other contacts that exist and are not joined to other objects
        """
        # Application has other contacts by default
        application = completed_application(user=self.user)
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

        other_contacts_form["other_contacts-has_other_contacts"] = "False"

        other_contacts_form["other_contacts-no_other_contacts_rationale"] = "Hello again!"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier has been removed from the database
        application = DomainApplication.objects.get()
        self.assertEqual(
            application.other_contacts.count(),
            0,
        )

        self.assertEquals(
            application.no_other_contacts_rationale,
            "Hello again!",
        )

    def test_submitting_no_other_contacts_rationale_removes_reference_other_contacts_when_joined(self):
        """When a user submits the Other Contacts form with no other contacts selected, the application's
        other contacts references get removed for other contacts that exist and are joined to other objects"""
        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(555) 555 5555",
        )
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
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # Now let's join the other contact to another object
        domain_info = DomainInformation.objects.create(creator=self.user)
        domain_info.other_contacts.set([other])

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

        other_contacts_form["other_contacts-has_other_contacts"] = "False"

        other_contacts_form["other_contacts-no_other_contacts_rationale"] = "Hello again!"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier is no longer associated with the application
        application = DomainApplication.objects.get()
        self.assertEqual(
            application.other_contacts.count(),
            0,
        )

        # Verify that the 'other' contact object still exists
        domain_info = DomainInformation.objects.get()
        self.assertEqual(
            domain_info.other_contacts.count(),
            1,
        )
        self.assertEqual(
            domain_info.other_contacts.all()[0].first_name,
            "Testy2",
        )

        self.assertEquals(
            application.no_other_contacts_rationale,
            "Hello again!",
        )

    def test_if_yes_no_form_is_no_then_no_other_contacts_required(self):
        """Applicants with no other contacts have to give a reason."""
        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        other_contacts_form = other_contacts_page.forms[0]
        other_contacts_form["other_contacts-has_other_contacts"] = "False"
        response = other_contacts_page.forms[0].submit()

        # The textarea for no other contacts returns this error message
        # Assert that it is returned, ie the no other contacts form is required
        self.assertContains(response, "Rationale for no other employees is required.")

        # The first name field for other contacts returns this error message
        # Assert that it is not returned, ie the contacts form is not required
        self.assertNotContains(response, "Enter the first name / given name of this contact.")

    def test_if_yes_no_form_is_yes_then_other_contacts_required(self):
        """Applicants with other contacts do not have to give a reason."""
        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        other_contacts_form = other_contacts_page.forms[0]
        other_contacts_form["other_contacts-has_other_contacts"] = "True"
        response = other_contacts_page.forms[0].submit()

        # The textarea for no other contacts returns this error message
        # Assert that it is not returned, ie the no other contacts form is not required
        self.assertNotContains(response, "Rationale for no other employees is required.")

        # The first name field for other contacts returns this error message
        # Assert that it is returned, ie the contacts form is required
        self.assertContains(response, "Enter the first name / given name of this contact.")

    def test_delete_other_contact(self):
        """Other contacts can be deleted after being saved to database.

        This formset uses the DJANGO DELETE widget. We'll test that by setting 2 contacts on an application,
        loading the form and marking one contact up for deletion."""
        # Populate the database with a domain application that
        # has 2 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        other2, _ = Contact.objects.get_or_create(
            first_name="Testy3",
            last_name="Tester3",
            title="Another Tester",
            email="testy3@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)
        application.other_contacts.add(other2)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded with both other contacts
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")
        self.assertEqual(other_contacts_form["other_contacts-1-first_name"].value, "Testy3")

        # Mark the first dude for deletion
        other_contacts_form.set("other_contacts-0-DELETE", "on")

        # Submit the form
        other_contacts_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the first dude was deleted
        application = DomainApplication.objects.get()
        self.assertEqual(application.other_contacts.count(), 1)
        self.assertEqual(application.other_contacts.first().first_name, "Testy3")

    def test_delete_other_contact_does_not_allow_zero_contacts(self):
        """Delete Other Contact does not allow submission with zero contacts."""
        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")

        # Mark the first dude for deletion
        other_contacts_form.set("other_contacts-0-DELETE", "on")

        # Submit the form
        other_contacts_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the contact was not deleted
        application = DomainApplication.objects.get()
        self.assertEqual(application.other_contacts.count(), 1)
        self.assertEqual(application.other_contacts.first().first_name, "Testy2")

    def test_delete_other_contact_sets_visible_empty_form_as_required_after_failed_submit(self):
        """When you:
            1. add an empty contact,
            2. delete existing contacts,
            3. then submit,
        The forms on page reload shows all the required fields and their errors."""

        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")

        # Set total forms to 2 indicating an additional formset was added.
        # Submit no data though for the second formset.
        # Set the first formset to be deleted.
        other_contacts_form["other_contacts-TOTAL_FORMS"] = "2"
        other_contacts_form.set("other_contacts-0-DELETE", "on")

        response = other_contacts_form.submit()

        # Assert that the response presents errors to the user, including to
        # Enter the first name ...
        self.assertContains(response, "Enter the first name / given name of this contact.")

    def test_edit_other_contact_in_place(self):
        """When you:
            1. edit an existing contact which is not joined to another model,
            2. then submit,
        The application is linked to the existing contact, and the existing contact updated."""

        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # other_contact_pk is the initial pk of the other contact. set it before update
        # to be able to verify after update that the same contact object is in place
        other_contact_pk = other.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")

        # update the first name of the contact
        other_contacts_form["other_contacts-0-first_name"] = "Testy3"

        # Submit the updated form
        other_contacts_form.submit()

        application.refresh_from_db()

        # assert that the Other Contact is updated "in place"
        other_contact = application.other_contacts.all()[0]
        self.assertEquals(other_contact_pk, other_contact.id)
        self.assertEquals("Testy3", other_contact.first_name)

    def test_edit_other_contact_creates_new(self):
        """When you:
            1. edit an existing contact which IS joined to another model,
            2. then submit,
        The application is linked to a new contact, and the new contact is updated."""

        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it, the other contact is also
        # the authorizing official initially
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(ao)

        # other_contact_pk is the initial pk of the other contact. set it before update
        # to be able to verify after update that the ao contact is still in place
        # and not updated, and that the new contact has a new id
        other_contact_pk = ao.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy")

        # update the first name of the contact
        other_contacts_form["other_contacts-0-first_name"] = "Testy2"

        # Submit the updated form
        other_contacts_form.submit()

        application.refresh_from_db()

        # assert that other contact info is updated, and that a new Contact
        # is created for the other contact
        other_contact = application.other_contacts.all()[0]
        self.assertNotEquals(other_contact_pk, other_contact.id)
        self.assertEquals("Testy2", other_contact.first_name)
        # assert that the authorizing official is not updated
        authorizing_official = application.authorizing_official
        self.assertEquals("Testy", authorizing_official.first_name)

    def test_edit_authorizing_official_in_place(self):
        """When you:
            1. edit an authorizing official which is not joined to another model,
            2. then submit,
        The application is linked to the existing ao, and the ao updated."""

        # Populate the database with a domain application that
        # has an authorizing_official (ao)
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            creator=self.user,
            status="started",
        )

        # ao_pk is the initial pk of the Authorizing Official. set it before update
        # to be able to verify after update that the same Contact object is in place
        ao_pk = ao.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_page = self.app.get(reverse("application:authorizing_official"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_form = ao_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(ao_form["authorizing_official-first_name"].value, "Testy")

        # update the first name of the contact
        ao_form["authorizing_official-first_name"] = "Testy2"

        # Submit the updated form
        ao_form.submit()

        application.refresh_from_db()

        # assert AO is updated "in place"
        updated_ao = application.authorizing_official
        self.assertEquals(ao_pk, updated_ao.id)
        self.assertEquals("Testy2", updated_ao.first_name)

    def test_edit_authorizing_official_creates_new(self):
        """When you:
            1. edit an existing authorizing official which IS joined to another model,
            2. then submit,
        The application is linked to a new Contact, and the new Contact is updated."""

        # Populate the database with a domain application that
        # has authorizing official assigned to it, the authorizing offical is also
        # an other contact initially
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(ao)

        # ao_pk is the initial pk of the authorizing official. set it before update
        # to be able to verify after update that the other contact is still in place
        # and not updated, and that the new ao has a new id
        ao_pk = ao.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_page = self.app.get(reverse("application:authorizing_official"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_form = ao_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(ao_form["authorizing_official-first_name"].value, "Testy")

        # update the first name of the contact
        ao_form["authorizing_official-first_name"] = "Testy2"

        # Submit the updated form
        ao_form.submit()

        application.refresh_from_db()

        # assert that the other contact is not updated
        other_contacts = application.other_contacts.all()
        other_contact = other_contacts[0]
        self.assertEquals(ao_pk, other_contact.id)
        self.assertEquals("Testy", other_contact.first_name)
        # assert that the authorizing official is updated
        authorizing_official = application.authorizing_official
        self.assertEquals("Testy2", authorizing_official.first_name)

    def test_edit_submitter_in_place(self):
        """When you:
            1. edit a submitter (your contact) which is not joined to another model,
            2. then submit,
        The application is linked to the existing submitter, and the submitter updated."""

        # Populate the database with a domain application that
        # has a submitter
        # We'll do it from scratch
        you, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            submitter=you,
            creator=self.user,
            status="started",
        )

        # submitter_pk is the initial pk of the submitter. set it before update
        # to be able to verify after update that the same contact object is in place
        submitter_pk = you.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_page = self.app.get(reverse("application:your_contact"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_form = your_contact_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(your_contact_form["your_contact-first_name"].value, "Testy")

        # update the first name of the contact
        your_contact_form["your_contact-first_name"] = "Testy2"

        # Submit the updated form
        your_contact_form.submit()

        application.refresh_from_db()

        updated_submitter = application.submitter
        self.assertEquals(submitter_pk, updated_submitter.id)
        self.assertEquals("Testy2", updated_submitter.first_name)

    def test_edit_submitter_creates_new(self):
        """When you:
            1. edit an existing your contact which IS joined to another model,
            2. then submit,
        The application is linked to a new Contact, and the new Contact is updated."""

        # Populate the database with a domain application that
        # has submitter assigned to it, the submitter is also
        # an other contact initially
        # We'll do it from scratch
        submitter, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            submitter=submitter,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(submitter)

        # submitter_pk is the initial pk of the your contact. set it before update
        # to be able to verify after update that the other contact is still in place
        # and not updated, and that the new submitter has a new id
        submitter_pk = submitter.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_page = self.app.get(reverse("application:your_contact"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_form = your_contact_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(your_contact_form["your_contact-first_name"].value, "Testy")

        # update the first name of the contact
        your_contact_form["your_contact-first_name"] = "Testy2"

        # Submit the updated form
        your_contact_form.submit()

        application.refresh_from_db()

        # assert that the other contact is not updated
        other_contacts = application.other_contacts.all()
        other_contact = other_contacts[0]
        self.assertEquals(submitter_pk, other_contact.id)
        self.assertEquals("Testy", other_contact.first_name)
        # assert that the submitter is updated
        submitter = application.submitter
        self.assertEquals("Testy2", submitter.first_name)

    def test_application_about_your_organiztion_interstate(self):
        """Special districts have to answer an additional question."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.INTERSTATE
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.ABOUT_YOUR_ORGANIZATION])

    def test_application_tribal_government(self):
        """Tribal organizations have to answer an additional question."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.TRIBAL
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # the tribal government page comes immediately afterwards
        self.assertIn("/tribal_government", type_result.headers["Location"])
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        tribal_government_page = type_result.follow()

        # and the step is on the sidebar list.
        self.assertContains(tribal_government_page, self.TITLES[Step.TRIBAL_GOVERNMENT])

    def test_application_ao_dynamic_text(self):
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        federal_form = federal_page.forms[0]
        federal_form["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        # federal agency so we have to fill in federal_agency
        org_contact_form["organization_contact-federal_agency"] = "General Services Administration"
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        # ---- AO CONTACT PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()
        self.assertContains(ao_page, "Executive branch federal agencies")

        # Go back to organization type page and change type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page.click(str(self.TITLES["organization_type"]), index=0)
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_form["organization_type-organization_type"] = "city"
        type_result = type_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()

        # Go back to AO page and test the dynamic text changed
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = election_page.click(str(self.TITLES["authorizing_official"]), index=0)
        self.assertContains(ao_page, "Domain requests from cities")

    def test_application_dotgov_domain_dynamic_text(self):
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        federal_form = federal_page.forms[0]
        federal_form["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        # federal agency so we have to fill in federal_agency
        org_contact_form["organization_contact-federal_agency"] = "General Services Administration"
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        # ---- AO CONTACT PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()

        # ---- AUTHORIZING OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()
        ao_form = ao_page.forms[0]
        ao_form["authorizing_official-first_name"] = "Testy ATO"
        ao_form["authorizing_official-last_name"] = "Tester ATO"
        ao_form["authorizing_official-title"] = "Chief Tester"
        ao_form["authorizing_official-email"] = "testy@town.com"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_result = ao_form.submit()

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = ao_result.follow()
        current_sites_form = current_sites_page.forms[0]
        current_sites_form["current_sites-0-website"] = "www.city.com"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()

        # ---- DOTGOV DOMAIN PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = current_sites_result.follow()

        self.assertContains(dotgov_page, "medicare.gov")

        # Go back to organization type page and change type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page.click(str(self.TITLES["organization_type"]), index=0)
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_form["organization_type-organization_type"] = "city"
        type_result = type_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()

        # Go back to dotgov domain page to test the dynamic text changed
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = election_page.click(str(self.TITLES["dotgov_domain"]), index=0)
        self.assertContains(dotgov_page, "CityofEudoraKS.gov")
        self.assertNotContains(dotgov_page, "medicare.gov")

    def test_application_formsets(self):
        """Users are able to add more than one of some fields."""
        current_sites_page = self.app.get(reverse("application:current_sites"))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        # fill in the form field
        current_sites_form = current_sites_page.forms[0]
        self.assertIn("current_sites-0-website", current_sites_form.fields)
        self.assertNotIn("current_sites-1-website", current_sites_form.fields)
        current_sites_form["current_sites-0-website"] = "https://example.com"

        # click "Add another"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit("submit_button", value="save")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_form = current_sites_result.follow().forms[0]

        # verify that there are two form fields
        value = current_sites_form["current_sites-0-website"].value
        self.assertEqual(value, "https://example.com")
        self.assertIn("current_sites-1-website", current_sites_form.fields)
        # and it is correctly referenced in the ManyToOne relationship
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(
            application.current_websites.filter(website="https://example.com").count(),
            1,
        )

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

    def test_long_org_name_in_application(self):
        """
        Make sure the long name is displaying in the application form,
        org step
        """
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()

        self.assertContains(type_page, "Federal: an agency of the U.S. government")

    def test_long_org_name_in_application_manage(self):
        """
        Make sure the long name is displaying in the application summary
        page (manage your application)
        """
        completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Edit" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "Federal: an agency of the U.S. government")

    def test_submit_modal_no_domain_text_fallback(self):
        """When user clicks on submit your domain request and the requested domain
        is null (possible through url direct access to the review page), present
        fallback copy in the modal's header.

        NOTE: This may be a moot point if we implement a more solid pattern in the
        future, like not a submit action at all on the review page."""

        review_page = self.app.get(reverse("application:review"))
        self.assertContains(review_page, "toggle-submit-domain-request")
        self.assertContains(review_page, "You are about to submit an incomplete request")


class TestWithDomainPermissions(TestWithUser):
    def setUp(self):
        super().setUp()
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.domain_with_ip, _ = Domain.objects.get_or_create(name="nameserverwithip.gov")
        self.domain_just_nameserver, _ = Domain.objects.get_or_create(name="justnameserver.com")
        self.domain_no_information, _ = Domain.objects.get_or_create(name="noinformation.gov")
        self.domain_on_hold, _ = Domain.objects.get_or_create(
            name="on-hold.gov",
            state=Domain.State.ON_HOLD,
            expiration_date=timezone.make_aware(
                datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
            ),
        )
        self.domain_deleted, _ = Domain.objects.get_or_create(
            name="deleted.gov",
            state=Domain.State.DELETED,
            expiration_date=timezone.make_aware(
                datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
            ),
        )

        self.domain_dsdata, _ = Domain.objects.get_or_create(name="dnssec-dsdata.gov")
        self.domain_multdsdata, _ = Domain.objects.get_or_create(name="dnssec-multdsdata.gov")
        # We could simply use domain (igorville) but this will be more readable in tests
        # that inherit this setUp
        self.domain_dnssec_none, _ = Domain.objects.get_or_create(name="dnssec-none.gov")

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain_dsdata)
        DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain_multdsdata)
        DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain_dnssec_none)
        DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain_with_ip)
        DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain_just_nameserver)
        DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain_on_hold)
        DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain_deleted)

        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

        UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain_dsdata, role=UserDomainRole.Roles.MANAGER
        )
        UserDomainRole.objects.get_or_create(
            user=self.user,
            domain=self.domain_multdsdata,
            role=UserDomainRole.Roles.MANAGER,
        )
        UserDomainRole.objects.get_or_create(
            user=self.user,
            domain=self.domain_dnssec_none,
            role=UserDomainRole.Roles.MANAGER,
        )
        UserDomainRole.objects.get_or_create(
            user=self.user,
            domain=self.domain_with_ip,
            role=UserDomainRole.Roles.MANAGER,
        )
        UserDomainRole.objects.get_or_create(
            user=self.user,
            domain=self.domain_just_nameserver,
            role=UserDomainRole.Roles.MANAGER,
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain_on_hold, role=UserDomainRole.Roles.MANAGER
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain_deleted, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        try:
            UserDomainRole.objects.all().delete()
            if hasattr(self.domain, "contacts"):
                self.domain.contacts.all().delete()
            DomainApplication.objects.all().delete()
            DomainInformation.objects.all().delete()
            PublicContact.objects.all().delete()
            HostIP.objects.all().delete()
            Host.objects.all().delete()
            Domain.objects.all().delete()
            UserDomainRole.objects.all().delete()
        except ValueError:  # pass if already deleted
            pass
        super().tearDown()


class TestDomainPermissions(TestWithDomainPermissions):
    def test_not_logged_in(self):
        """Not logged in gets a redirect to Login."""
        for view_name in [
            "domain",
            "domain-users",
            "domain-users-add",
            "domain-dns-nameservers",
            "domain-org-name-address",
            "domain-authorizing-official",
            "domain-your-contact-information",
            "domain-security-email",
        ]:
            with self.subTest(view_name=view_name):
                response = self.client.get(reverse(view_name, kwargs={"pk": self.domain.id}))
                self.assertEqual(response.status_code, 302)

    def test_no_domain_role(self):
        """Logged in but no role gets 403 Forbidden."""
        self.client.force_login(self.user)
        self.role.delete()  # user no longer has a role on this domain

        for view_name in [
            "domain",
            "domain-users",
            "domain-users-add",
            "domain-dns-nameservers",
            "domain-org-name-address",
            "domain-authorizing-official",
            "domain-your-contact-information",
            "domain-security-email",
        ]:
            with self.subTest(view_name=view_name):
                with less_console_noise():
                    response = self.client.get(reverse(view_name, kwargs={"pk": self.domain.id}))
                self.assertEqual(response.status_code, 403)

    def test_domain_pages_blocked_for_on_hold_and_deleted(self):
        """Test that the domain pages are blocked for on hold and deleted domains"""

        self.client.force_login(self.user)
        for view_name in [
            "domain-users",
            "domain-users-add",
            "domain-dns",
            "domain-dns-nameservers",
            "domain-dns-dnssec",
            "domain-dns-dnssec-dsdata",
            "domain-org-name-address",
            "domain-authorizing-official",
            "domain-your-contact-information",
            "domain-security-email",
        ]:
            for domain in [
                self.domain_on_hold,
                self.domain_deleted,
            ]:
                with self.subTest(view_name=view_name, domain=domain):
                    with less_console_noise():
                        response = self.client.get(reverse(view_name, kwargs={"pk": domain.id}))
                        self.assertEqual(response.status_code, 403)


class TestDomainOverview(TestWithDomainPermissions, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.client.force_login(self.user)


class TestDomainDetail(TestDomainOverview):
    @skip("Assertion broke for no reason, why? Need to fix")
    def test_domain_detail_link_works(self):
        home_page = self.app.get("/")
        logger.info(f"This is the value of home_page: {home_page}")
        self.assertContains(home_page, "igorville.gov")
        # click the "Edit" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "igorville.gov")
        self.assertContains(detail_page, "Status")

    def test_unknown_domain_does_not_show_as_expired_on_homepage(self):
        """An UNKNOWN domain does not show as expired on the homepage.
        It shows as 'DNS needed'"""
        # At the time of this test's writing, there are 6 UNKNOWN domains inherited
        # from constructors. Let's reset.
        Domain.objects.all().delete()
        UserDomainRole.objects.all().delete()
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        home_page = self.app.get("/")
        self.assertNotContains(home_page, "igorville.gov")
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )
        home_page = self.app.get("/")
        self.assertContains(home_page, "igorville.gov")
        igorville = Domain.objects.get(name="igorville.gov")
        self.assertEquals(igorville.state, Domain.State.UNKNOWN)
        self.assertNotContains(home_page, "Expired")
        self.assertContains(home_page, "DNS needed")

    def test_unknown_domain_does_not_show_as_expired_on_detail_page(self):
        """An UNKNOWN domain does not show as expired on the detail page.
        It shows as 'DNS needed'"""
        # At the time of this test's writing, there are 6 UNKNOWN domains inherited
        # from constructors. Let's reset.
        Domain.objects.all().delete()
        UserDomainRole.objects.all().delete()

        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

        home_page = self.app.get("/")
        self.assertContains(home_page, "igorville.gov")
        igorville = Domain.objects.get(name="igorville.gov")
        self.assertEquals(igorville.state, Domain.State.UNKNOWN)
        detail_page = home_page.click("Manage", index=0)
        self.assertNotContains(detail_page, "Expired")

        self.assertContains(detail_page, "DNS needed")

    def test_domain_detail_blocked_for_ineligible_user(self):
        """We could easily duplicate this test for all domain management
        views, but a single url test should be solid enough since all domain
        management pages share the same permissions class"""
        self.user.status = User.RESTRICTED
        self.user.save()
        home_page = self.app.get("/")
        self.assertContains(home_page, "igorville.gov")
        with less_console_noise():
            response = self.client.get(reverse("domain", kwargs={"pk": self.domain.id}))
            self.assertEqual(response.status_code, 403)

    def test_domain_detail_allowed_for_on_hold(self):
        """Test that the domain overview page displays for on hold domain"""
        home_page = self.app.get("/")
        self.assertContains(home_page, "on-hold.gov")

        # View domain overview page
        detail_page = self.client.get(reverse("domain", kwargs={"pk": self.domain_on_hold.id}))
        self.assertNotContains(detail_page, "Edit")

    def test_domain_detail_see_just_nameserver(self):
        home_page = self.app.get("/")
        self.assertContains(home_page, "justnameserver.com")

        # View nameserver on Domain Overview page
        detail_page = self.app.get(reverse("domain", kwargs={"pk": self.domain_just_nameserver.id}))

        self.assertContains(detail_page, "justnameserver.com")
        self.assertContains(detail_page, "ns1.justnameserver.com")
        self.assertContains(detail_page, "ns2.justnameserver.com")

    def test_domain_detail_see_nameserver_and_ip(self):
        home_page = self.app.get("/")
        self.assertContains(home_page, "nameserverwithip.gov")

        # View nameserver on Domain Overview page
        detail_page = self.app.get(reverse("domain", kwargs={"pk": self.domain_with_ip.id}))

        self.assertContains(detail_page, "nameserverwithip.gov")

        self.assertContains(detail_page, "ns1.nameserverwithip.gov")
        self.assertContains(detail_page, "ns2.nameserverwithip.gov")
        self.assertContains(detail_page, "ns3.nameserverwithip.gov")
        # Splitting IP addresses bc there is odd whitespace and can't strip text
        self.assertContains(detail_page, "(1.2.3.4,")
        self.assertContains(detail_page, "2.3.4.5)")

    def test_domain_detail_with_no_information_or_application(self):
        """Test that domain management page returns 200 and displays error
        when no domain information or domain application exist"""
        # have to use staff user for this test
        staff_user = create_user()
        # staff_user.save()
        self.client.force_login(staff_user)

        # need to set the analyst_action and analyst_action_location
        # in the session to emulate user clicking Manage Domain
        # in the admin interface
        session = self.client.session
        session["analyst_action"] = "foo"
        session["analyst_action_location"] = self.domain_no_information.id
        session.save()

        detail_page = self.client.get(reverse("domain", kwargs={"pk": self.domain_no_information.id}))

        self.assertContains(detail_page, "noinformation.gov")
        self.assertContains(detail_page, "Domain missing domain information")


class TestDomainManagers(TestDomainOverview):
    def tearDown(self):
        """Ensure that the user has its original permissions"""
        super().tearDown()
        self.user.is_staff = False
        self.user.save()
        User.objects.all().delete()

    def test_domain_managers(self):
        response = self.client.get(reverse("domain-users", kwargs={"pk": self.domain.id}))
        self.assertContains(response, "Domain managers")

    def test_domain_managers_add_link(self):
        """Button to get to user add page works."""
        management_page = self.app.get(reverse("domain-users", kwargs={"pk": self.domain.id}))
        add_page = management_page.click("Add a domain manager")
        self.assertContains(add_page, "Add a domain manager")

    def test_domain_user_add(self):
        response = self.client.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
        self.assertContains(response, "Add a domain manager")

    def test_domain_user_delete_link(self):
        """Tests if the user delete link works"""

        # Add additional users
        dummy_user_1 = User.objects.create(
            username="macncheese",
            email="cheese@igorville.com",
        )
        dummy_user_2 = User.objects.create(
            username="pastapizza",
            email="pasta@igorville.com",
        )

        role_1 = UserDomainRole.objects.create(user=dummy_user_1, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        role_2 = UserDomainRole.objects.create(user=dummy_user_2, domain=self.domain, role=UserDomainRole.Roles.MANAGER)

        response = self.client.get(reverse("domain-users", kwargs={"pk": self.domain.id}))

        # Make sure we're on the right page
        self.assertContains(response, "Domain managers")

        # Make sure the desired user exists
        self.assertContains(response, "cheese@igorville.com")

        # Delete dummy_user_1
        response = self.client.post(
            reverse("domain-user-delete", kwargs={"pk": self.domain.id, "user_pk": dummy_user_1.id}), follow=True
        )

        # Grab the displayed messages
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)

        # Ensure the error we recieve is in line with what we expect
        message = messages[0]
        self.assertEqual(message.message, "Removed cheese@igorville.com as a manager for this domain.")
        self.assertEqual(message.tags, "success")

        # Check that role_1 deleted in the DB after the post
        deleted_user_exists = UserDomainRole.objects.filter(id=role_1.id).exists()
        self.assertFalse(deleted_user_exists)

        # Ensure that the current user wasn't deleted
        current_user_exists = UserDomainRole.objects.filter(user=self.user.id, domain=self.domain).exists()
        self.assertTrue(current_user_exists)

        # Ensure that the other userdomainrole was not deleted
        role_2_exists = UserDomainRole.objects.filter(id=role_2.id).exists()
        self.assertTrue(role_2_exists)

    def test_domain_user_delete_self_redirects_home(self):
        """Tests if deleting yourself redirects to home"""
        # Add additional users
        dummy_user_1 = User.objects.create(
            username="macncheese",
            email="cheese@igorville.com",
        )
        dummy_user_2 = User.objects.create(
            username="pastapizza",
            email="pasta@igorville.com",
        )

        role_1 = UserDomainRole.objects.create(user=dummy_user_1, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        role_2 = UserDomainRole.objects.create(user=dummy_user_2, domain=self.domain, role=UserDomainRole.Roles.MANAGER)

        response = self.client.get(reverse("domain-users", kwargs={"pk": self.domain.id}))

        # Make sure we're on the right page
        self.assertContains(response, "Domain managers")

        # Make sure the desired user exists
        self.assertContains(response, "info@example.com")

        # Make sure more than one UserDomainRole exists on this object
        self.assertContains(response, "cheese@igorville.com")

        # Delete the current user
        response = self.client.post(
            reverse("domain-user-delete", kwargs={"pk": self.domain.id, "user_pk": self.user.id}), follow=True
        )

        # Check if we've been redirected to the home page
        self.assertContains(response, "Manage your domains")

        # Grab the displayed messages
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)

        # Ensure the error we recieve is in line with what we expect
        message = messages[0]
        self.assertEqual(message.message, "You are no longer managing the domain igorville.gov.")
        self.assertEqual(message.tags, "success")

        # Ensure that the current user was deleted
        current_user_exists = UserDomainRole.objects.filter(user=self.user.id, domain=self.domain).exists()
        self.assertFalse(current_user_exists)

        # Ensure that the other userdomainroles are not deleted
        role_1_exists = UserDomainRole.objects.filter(id=role_1.id).exists()
        self.assertTrue(role_1_exists)

        role_2_exists = UserDomainRole.objects.filter(id=role_2.id).exists()
        self.assertTrue(role_2_exists)

    @boto3_mocking.patching
    def test_domain_user_add_form(self):
        """Adding an existing user works."""
        other_user, _ = get_user_model().objects.get_or_create(email="mayor@igorville.gov")
        add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        add_page.form["email"] = "mayor@igorville.gov"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                success_result = add_page.form.submit()

        self.assertEqual(success_result.status_code, 302)
        self.assertEqual(
            success_result["Location"],
            reverse("domain-users", kwargs={"pk": self.domain.id}),
        )

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        success_page = success_result.follow()
        self.assertContains(success_page, "mayor@igorville.gov")

    @boto3_mocking.patching
    def test_domain_invitation_created(self):
        """Add user on a nonexistent email creates an invitation.

        Adding a non-existent user sends an email as a side-effect, so mock
        out the boto3 SES email sending here.
        """
        # make sure there is no user with this email
        email_address = "mayor@igorville.gov"
        User.objects.filter(email=email_address).delete()

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        add_page.form["email"] = email_address
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                success_result = add_page.form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        success_page = success_result.follow()

        self.assertContains(success_page, email_address)
        self.assertContains(success_page, "Cancel")  # link to cancel invitation
        self.assertTrue(DomainInvitation.objects.filter(email=email_address).exists())

    @boto3_mocking.patching
    def test_domain_invitation_created_for_caps_email(self):
        """Add user on a nonexistent email with CAPS creates an invitation to lowercase email.

        Adding a non-existent user sends an email as a side-effect, so mock
        out the boto3 SES email sending here.
        """
        # make sure there is no user with this email
        email_address = "mayor@igorville.gov"
        caps_email_address = "MAYOR@igorville.gov"
        User.objects.filter(email=email_address).delete()

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        add_page.form["email"] = caps_email_address
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                success_result = add_page.form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        success_page = success_result.follow()

        self.assertContains(success_page, email_address)
        self.assertContains(success_page, "Cancel")  # link to cancel invitation
        self.assertTrue(DomainInvitation.objects.filter(email=email_address).exists())

    @boto3_mocking.patching
    def test_domain_invitation_email_sent(self):
        """Inviting a non-existent user sends them an email."""
        # make sure there is no user with this email
        email_address = "mayor@igorville.gov"
        User.objects.filter(email=email_address).delete()

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
                session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                add_page.form["email"] = email_address
                self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                add_page.form.submit()

        # check the mock instance to see if `send_email` was called right
        mock_client_instance.send_email.assert_called_once_with(
            FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            Destination={"ToAddresses": [email_address]},
            Content=ANY,
        )

    @boto3_mocking.patching
    def test_domain_invitation_email_has_email_as_requestor_non_existent(self):
        """Inviting a non existent user sends them an email, with email as the name."""
        # make sure there is no user with this email
        email_address = "mayor@igorville.gov"
        User.objects.filter(email=email_address).delete()

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
                session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                add_page.form["email"] = email_address
                self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                add_page.form.submit()

        # check the mock instance to see if `send_email` was called right
        mock_client_instance.send_email.assert_called_once_with(
            FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            Destination={"ToAddresses": [email_address]},
            Content=ANY,
        )

        # Check the arguments passed to send_email method
        _, kwargs = mock_client_instance.send_email.call_args

        # Extract the email content, and check that the message is as we expect
        email_content = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("info@example.com", email_content)

        # Check that the requestors first/last name do not exist
        self.assertNotIn("First", email_content)
        self.assertNotIn("Last", email_content)
        self.assertNotIn("First Last", email_content)

    @boto3_mocking.patching
    def test_domain_invitation_email_has_email_as_requestor(self):
        """Inviting a user sends them an email, with email as the name."""
        # Create a fake user object
        email_address = "mayor@igorville.gov"
        User.objects.get_or_create(email=email_address, username="fakeuser@fakeymail.com")

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
                session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                add_page.form["email"] = email_address
                self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                add_page.form.submit()

        # check the mock instance to see if `send_email` was called right
        mock_client_instance.send_email.assert_called_once_with(
            FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            Destination={"ToAddresses": [email_address]},
            Content=ANY,
        )

        # Check the arguments passed to send_email method
        _, kwargs = mock_client_instance.send_email.call_args

        # Extract the email content, and check that the message is as we expect
        email_content = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("info@example.com", email_content)

        # Check that the requestors first/last name do not exist
        self.assertNotIn("First", email_content)
        self.assertNotIn("Last", email_content)
        self.assertNotIn("First Last", email_content)

    @boto3_mocking.patching
    def test_domain_invitation_email_has_email_as_requestor_staff(self):
        """Inviting a user sends them an email, with email as the name."""
        # Create a fake user object
        email_address = "mayor@igorville.gov"
        User.objects.get_or_create(email=email_address, username="fakeuser@fakeymail.com")

        # Make sure the user is staff
        self.user.is_staff = True
        self.user.save()

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
                session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                add_page.form["email"] = email_address
                self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                add_page.form.submit()

        # check the mock instance to see if `send_email` was called right
        mock_client_instance.send_email.assert_called_once_with(
            FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            Destination={"ToAddresses": [email_address]},
            Content=ANY,
        )

        # Check the arguments passed to send_email method
        _, kwargs = mock_client_instance.send_email.call_args

        # Extract the email content, and check that the message is as we expect
        email_content = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("help@get.gov", email_content)

        # Check that the requestors first/last name do not exist
        self.assertNotIn("First", email_content)
        self.assertNotIn("Last", email_content)
        self.assertNotIn("First Last", email_content)

    @boto3_mocking.patching
    def test_domain_invitation_email_displays_error_non_existent(self):
        """Inviting a non existent user sends them an email, with email as the name."""
        # make sure there is no user with this email
        email_address = "mayor@igorville.gov"
        User.objects.filter(email=email_address).delete()

        # Give the user who is sending the email an invalid email address
        self.user.email = ""
        self.user.save()

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        mock_client = MagicMock()
        mock_error_message = MagicMock()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with patch("django.contrib.messages.error") as mock_error_message:
                with less_console_noise():
                    add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
                    session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                    add_page.form["email"] = email_address
                    self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                    add_page.form.submit().follow()

        expected_message_content = "Can't send invitation email. No email is associated with your account."

        # Grab the message content
        returned_error_message = mock_error_message.call_args[0][1]

        # Check that the message content is what we expect
        self.assertEqual(expected_message_content, returned_error_message)

    @boto3_mocking.patching
    def test_domain_invitation_email_displays_error(self):
        """When the requesting user has no email, an error is displayed"""
        # make sure there is no user with this email
        # Create a fake user object
        email_address = "mayor@igorville.gov"
        User.objects.get_or_create(email=email_address, username="fakeuser@fakeymail.com")

        # Give the user who is sending the email an invalid email address
        self.user.email = ""
        self.user.save()

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        mock_client = MagicMock()

        mock_error_message = MagicMock()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with patch("django.contrib.messages.error") as mock_error_message:
                with less_console_noise():
                    add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))
                    session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                    add_page.form["email"] = email_address
                    self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                    add_page.form.submit().follow()

        expected_message_content = "Can't send invitation email. No email is associated with your account."

        # Grab the message content
        returned_error_message = mock_error_message.call_args[0][1]

        # Check that the message content is what we expect
        self.assertEqual(expected_message_content, returned_error_message)

    def test_domain_invitation_cancel(self):
        """Posting to the delete view deletes an invitation."""
        email_address = "mayor@igorville.gov"
        invitation, _ = DomainInvitation.objects.get_or_create(domain=self.domain, email=email_address)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                self.client.post(reverse("invitation-delete", kwargs={"pk": invitation.id}))
        mock_client.EMAILS_SENT.clear()
        with self.assertRaises(DomainInvitation.DoesNotExist):
            DomainInvitation.objects.get(id=invitation.id)

    def test_domain_invitation_cancel_no_permissions(self):
        """Posting to the delete view as a different user should fail."""
        email_address = "mayor@igorville.gov"
        invitation, _ = DomainInvitation.objects.get_or_create(domain=self.domain, email=email_address)

        other_user = User()
        other_user.save()
        self.client.force_login(other_user)
        mock_client = MagicMock()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():  # permission denied makes console errors
                result = self.client.post(reverse("invitation-delete", kwargs={"pk": invitation.id}))

        self.assertEqual(result.status_code, 403)

    @boto3_mocking.patching
    def test_domain_invitation_flow(self):
        """Send an invitation to a new user, log in and load the dashboard."""
        email_address = "mayor@igorville.gov"
        User.objects.filter(email=email_address).delete()

        add_page = self.app.get(reverse("domain-users-add", kwargs={"pk": self.domain.id}))

        self.domain_information, _ = DomainInformation.objects.get_or_create(creator=self.user, domain=self.domain)

        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        add_page.form["email"] = email_address
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        mock_client = MagicMock()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                add_page.form.submit()

        # user was invited, create them
        new_user = User.objects.create(username=email_address, email=email_address)
        # log them in to `self.app`
        self.app.set_user(new_user.username)
        # and manually call the on each login callback
        new_user.on_each_login()

        # Now load the home page and make sure our domain appears there
        home_page = self.app.get(reverse("home"))
        self.assertContains(home_page, self.domain.name)


class TestDomainNameservers(TestDomainOverview):
    def test_domain_nameservers(self):
        """Can load domain's nameservers page."""
        page = self.client.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        self.assertContains(page, "DNS name servers")

    def test_domain_nameservers_form_submit_one_nameserver(self):
        """Nameserver form submitted with one nameserver throws error.

        Uses self.app WebTest because we need to interact with forms.
        """
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form with only one nameserver, should error
        # regarding required fields
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the required field.  form requires a minimum of 2 name servers
        self.assertContains(
            result,
            "At least two name servers are required.",
            count=2,
            status_code=200,
        )

    def test_domain_nameservers_form_submit_subdomain_missing_ip(self):
        """Nameserver form catches missing ip error on subdomain.

        Uses self.app WebTest because we need to interact with forms.
        """
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form without two hosts, both subdomains,
        # only one has ips
        nameservers_page.form["form-1-server"] = "ns2.igorville.gov"

        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the required field.  subdomain missing an ip
        self.assertContains(
            result,
            str(NameserverError(code=NameserverErrorCodes.MISSING_IP)),
            count=2,
            status_code=200,
        )

    def test_domain_nameservers_form_submit_missing_host(self):
        """Nameserver form catches error when host is missing.

        Uses self.app WebTest because we need to interact with forms.
        """
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form without two hosts, both subdomains,
        # only one has ips
        nameservers_page.form["form-1-ip"] = "127.0.0.1"
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the required field.  nameserver has ip but missing host
        self.assertContains(
            result,
            str(NameserverError(code=NameserverErrorCodes.MISSING_HOST)),
            count=2,
            status_code=200,
        )

    def test_domain_nameservers_form_submit_duplicate_host(self):
        """Nameserver form catches error when host is duplicated.

        Uses self.app WebTest because we need to interact with forms.
        """
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form with duplicate host names of fake.host.com
        nameservers_page.form["form-0-ip"] = ""
        nameservers_page.form["form-1-server"] = "fake.host.com"
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the required field.  remove duplicate entry
        self.assertContains(
            result,
            str(NameserverError(code=NameserverErrorCodes.DUPLICATE_HOST)),
            count=2,
            status_code=200,
        )

    def test_domain_nameservers_form_submit_whitespace(self):
        """Nameserver form removes whitespace from ip.

        Uses self.app WebTest because we need to interact with forms.
        """
        nameserver1 = "ns1.igorville.gov"
        nameserver2 = "ns2.igorville.gov"
        valid_ip = "1.1. 1.1"
        # initial nameservers page has one server with two ips
        # have to throw an error in order to test that the whitespace has been stripped from ip
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form without one host and an ip with whitespace
        nameservers_page.form["form-0-server"] = nameserver1
        nameservers_page.form["form-1-ip"] = valid_ip
        nameservers_page.form["form-1-server"] = nameserver2
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an ip address which has been stripped of whitespace,
        # response should be a 302 to success page
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}),
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        page = result.follow()
        # in the event of a generic nameserver error from registry error, there will be a 302
        # with an error message displayed, so need to follow 302 and test for success message
        self.assertContains(page, "The name servers for this domain have been updated")

    def test_domain_nameservers_form_submit_glue_record_not_allowed(self):
        """Nameserver form catches error when IP is present
        but host not subdomain.

        Uses self.app WebTest because we need to interact with forms.
        """
        nameserver1 = "ns1.igorville.gov"
        nameserver2 = "ns2.igorville.com"
        valid_ip = "127.0.0.1"
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form without two hosts, both subdomains,
        # only one has ips
        nameservers_page.form["form-0-server"] = nameserver1
        nameservers_page.form["form-1-server"] = nameserver2
        nameservers_page.form["form-1-ip"] = valid_ip
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the required field.  nameserver has ip but missing host
        self.assertContains(
            result,
            str(NameserverError(code=NameserverErrorCodes.GLUE_RECORD_NOT_ALLOWED)),
            count=2,
            status_code=200,
        )

    def test_domain_nameservers_form_submit_invalid_ip(self):
        """Nameserver form catches invalid IP on submission.

        Uses self.app WebTest because we need to interact with forms.
        """
        nameserver = "ns2.igorville.gov"
        invalid_ip = "123"
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form without two hosts, both subdomains,
        # only one has ips
        nameservers_page.form["form-1-server"] = nameserver
        nameservers_page.form["form-1-ip"] = invalid_ip
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the required field.  nameserver has ip but missing host
        self.assertContains(
            result,
            str(NameserverError(code=NameserverErrorCodes.INVALID_IP, nameserver=nameserver)),
            count=2,
            status_code=200,
        )

    def test_domain_nameservers_form_submit_invalid_host(self):
        """Nameserver form catches invalid host on submission.

        Uses self.app WebTest because we need to interact with forms.
        """
        nameserver = "invalid-nameserver.gov"
        valid_ip = "123.2.45.111"
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form without two hosts, both subdomains,
        # only one has ips
        nameservers_page.form["form-1-server"] = nameserver
        nameservers_page.form["form-1-ip"] = valid_ip
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the required field.  nameserver has invalid host
        self.assertContains(
            result,
            str(NameserverError(code=NameserverErrorCodes.INVALID_HOST, nameserver=nameserver)),
            count=2,
            status_code=200,
        )

    def test_domain_nameservers_form_submits_successfully(self):
        """Nameserver form submits successfully with valid input.

        Uses self.app WebTest because we need to interact with forms.
        """
        nameserver1 = "ns1.igorville.gov"
        nameserver2 = "ns2.igorville.gov"
        valid_ip = "127.0.0.1"
        # initial nameservers page has one server with two ips
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # attempt to submit the form without two hosts, both subdomains,
        # only one has ips
        nameservers_page.form["form-0-server"] = nameserver1
        nameservers_page.form["form-1-server"] = nameserver2
        nameservers_page.form["form-1-ip"] = valid_ip
        with less_console_noise():  # swallow log warning message
            result = nameservers_page.form.submit()
        # form submission was a successful post, response should be a 302
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}),
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        page = result.follow()
        self.assertContains(page, "The name servers for this domain have been updated")

    def test_domain_nameservers_form_invalid(self):
        """Nameserver form does not submit with invalid data.

        Uses self.app WebTest because we need to interact with forms.
        """
        nameservers_page = self.app.get(reverse("domain-dns-nameservers", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # first two nameservers are required, so if we empty one out we should
        # get a form error
        nameservers_page.form["form-0-server"] = ""
        with less_console_noise():  # swallow logged warning message
            result = nameservers_page.form.submit()
        # form submission was a post with an error, response should be a 200
        # error text appears four times, twice at the top of the page,
        # once around each required field.
        self.assertContains(
            result,
            "At least two name servers are required.",
            count=4,
            status_code=200,
        )


class TestDomainAuthorizingOfficial(TestDomainOverview):
    def test_domain_authorizing_official(self):
        """Can load domain's authorizing official page."""
        page = self.client.get(reverse("domain-authorizing-official", kwargs={"pk": self.domain.id}))
        # once on the sidebar, once in the title
        self.assertContains(page, "Authorizing official", count=2)

    def test_domain_authorizing_official_content(self):
        """Authorizing official information appears on the page."""
        self.domain_information.authorizing_official = Contact(first_name="Testy")
        self.domain_information.authorizing_official.save()
        self.domain_information.save()
        page = self.app.get(reverse("domain-authorizing-official", kwargs={"pk": self.domain.id}))
        self.assertContains(page, "Testy")

    def test_domain_edit_authorizing_official_in_place(self):
        """When editing an authorizing official for domain information and AO is not
        joined to any other objects"""
        self.domain_information.authorizing_official = Contact(
            first_name="Testy", last_name="Tester", title="CIO", email="nobody@igorville.gov"
        )
        self.domain_information.authorizing_official.save()
        self.domain_information.save()
        ao_page = self.app.get(reverse("domain-authorizing-official", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_form = ao_page.forms[0]
        self.assertEqual(ao_form["first_name"].value, "Testy")
        ao_form["first_name"] = "Testy2"
        # ao_pk is the initial pk of the authorizing official. set it before update
        # to be able to verify after update that the same contact object is in place
        ao_pk = self.domain_information.authorizing_official.id
        ao_form.submit()

        # refresh domain information
        self.domain_information.refresh_from_db()
        self.assertEqual("Testy2", self.domain_information.authorizing_official.first_name)
        self.assertEqual(ao_pk, self.domain_information.authorizing_official.id)

    def test_domain_edit_authorizing_official_creates_new(self):
        """When editing an authorizing official for domain information and AO IS
        joined to another object"""
        # set AO and Other Contact to the same Contact object
        self.domain_information.authorizing_official = Contact(
            first_name="Testy", last_name="Tester", title="CIO", email="nobody@igorville.gov"
        )
        self.domain_information.authorizing_official.save()
        self.domain_information.save()
        self.domain_information.other_contacts.add(self.domain_information.authorizing_official)
        self.domain_information.save()
        # load the Authorizing Official in the web form
        ao_page = self.app.get(reverse("domain-authorizing-official", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_form = ao_page.forms[0]
        # verify the first name is "Testy" and then change it to "Testy2"
        self.assertEqual(ao_form["first_name"].value, "Testy")
        ao_form["first_name"] = "Testy2"
        # ao_pk is the initial pk of the authorizing official. set it before update
        # to be able to verify after update that the same contact object is in place
        ao_pk = self.domain_information.authorizing_official.id
        ao_form.submit()

        # refresh domain information
        self.domain_information.refresh_from_db()
        # assert that AO information is updated, and that the AO is a new Contact
        self.assertEqual("Testy2", self.domain_information.authorizing_official.first_name)
        self.assertNotEqual(ao_pk, self.domain_information.authorizing_official.id)
        # assert that the Other Contact information is not updated and that the Other Contact
        # is the original Contact object
        other_contact = self.domain_information.other_contacts.all()[0]
        self.assertEqual("Testy", other_contact.first_name)
        self.assertEqual(ao_pk, other_contact.id)


class TestDomainOrganization(TestDomainOverview):
    def test_domain_org_name_address(self):
        """Can load domain's org name and mailing address page."""
        page = self.client.get(reverse("domain-org-name-address", kwargs={"pk": self.domain.id}))
        # once on the sidebar, once in the page title, once as H1
        self.assertContains(page, "Organization name and mailing address", count=3)

    def test_domain_org_name_address_content(self):
        """Org name and address information appears on the page."""
        self.domain_information.organization_name = "Town of Igorville"
        self.domain_information.save()
        page = self.app.get(reverse("domain-org-name-address", kwargs={"pk": self.domain.id}))
        self.assertContains(page, "Town of Igorville")

    def test_domain_org_name_address_form(self):
        """Submitting changes works on the org name address page."""
        self.domain_information.organization_name = "Town of Igorville"
        self.domain_information.save()
        org_name_page = self.app.get(reverse("domain-org-name-address", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        org_name_page.form["organization_name"] = "Not igorville"
        org_name_page.form["city"] = "Faketown"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        success_result_page = org_name_page.form.submit()
        self.assertEqual(success_result_page.status_code, 200)

        self.assertContains(success_result_page, "Not igorville")
        self.assertContains(success_result_page, "Faketown")


class TestDomainContactInformation(TestDomainOverview):
    def test_domain_your_contact_information(self):
        """Can load domain's your contact information page."""
        page = self.client.get(reverse("domain-your-contact-information", kwargs={"pk": self.domain.id}))
        self.assertContains(page, "Your contact information")

    def test_domain_your_contact_information_content(self):
        """Logged-in user's contact information appears on the page."""
        self.user.contact.first_name = "Testy"
        self.user.contact.save()
        page = self.app.get(reverse("domain-your-contact-information", kwargs={"pk": self.domain.id}))
        self.assertContains(page, "Testy")


class TestDomainSecurityEmail(TestDomainOverview):
    def test_domain_security_email_existing_security_contact(self):
        """Can load domain's security email page."""
        self.mockSendPatch = patch("registrar.models.domain.registry.send")
        self.mockedSendFunction = self.mockSendPatch.start()
        self.mockedSendFunction.side_effect = self.mockSend

        domain_contact, _ = Domain.objects.get_or_create(name="freeman.gov")
        # Add current user to this domain
        _ = UserDomainRole(user=self.user, domain=domain_contact, role="admin").save()
        page = self.client.get(reverse("domain-security-email", kwargs={"pk": domain_contact.id}))

        # Loads correctly
        self.assertContains(page, "Security email")
        self.assertContains(page, "security@mail.gov")
        self.mockSendPatch.stop()

    def test_domain_security_email_no_security_contact(self):
        """Loads a domain with no defined security email.
        We should not show the default."""
        self.mockSendPatch = patch("registrar.models.domain.registry.send")
        self.mockedSendFunction = self.mockSendPatch.start()
        self.mockedSendFunction.side_effect = self.mockSend

        page = self.client.get(reverse("domain-security-email", kwargs={"pk": self.domain.id}))

        # Loads correctly
        self.assertContains(page, "Security email")
        self.assertNotContains(page, "dotgov@cisa.dhs.gov")
        self.mockSendPatch.stop()

    def test_domain_security_email(self):
        """Can load domain's security email page."""
        page = self.client.get(reverse("domain-security-email", kwargs={"pk": self.domain.id}))
        self.assertContains(page, "Security email")

    def test_domain_security_email_form(self):
        """Adding a security email works.
        Uses self.app WebTest because we need to interact with forms.
        """
        security_email_page = self.app.get(reverse("domain-security-email", kwargs={"pk": self.domain.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        security_email_page.form["security_email"] = "mayor@igorville.gov"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        mock_client = MagicMock()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():  # swallow log warning message
                result = security_email_page.form.submit()
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            reverse("domain-security-email", kwargs={"pk": self.domain.id}),
        )

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        success_page = result.follow()
        self.assertContains(success_page, "The security email for this domain has been updated")

    def test_security_email_form_messages(self):
        """
        Test against the success and error messages that are defined in the view
        """
        p = "adminpass"
        self.client.login(username="superuser", password=p)

        form_data_registry_error = {
            "security_email": "test@failCreate.gov",
        }

        form_data_contact_error = {
            "security_email": "test@contactError.gov",
        }

        form_data_success = {
            "security_email": "test@something.gov",
        }

        test_cases = [
            (
                "RegistryError",
                form_data_registry_error,
                str(GenericError(code=GenericErrorCodes.CANNOT_CONTACT_REGISTRY)),
            ),
            (
                "ContactError",
                form_data_contact_error,
                str(SecurityEmailError(code=SecurityEmailErrorCodes.BAD_DATA)),
            ),
            (
                "RegistrySuccess",
                form_data_success,
                "The security email for this domain has been updated.",
            ),
            # Add more test cases with different scenarios here
        ]

        for test_name, data, expected_message in test_cases:
            response = self.client.post(
                reverse("domain-security-email", kwargs={"pk": self.domain.id}),
                data=data,
                follow=True,
            )

            # Check the response status code, content, or any other relevant assertions
            self.assertEqual(response.status_code, 200)

            # Check if the expected message tag is set
            if test_name == "RegistryError" or test_name == "ContactError":
                message_tag = "error"
            elif test_name == "RegistrySuccess":
                message_tag = "success"
            else:
                # Handle other cases if needed
                message_tag = "info"  # Change to the appropriate default

            # Check the message tag
            messages = list(response.context["messages"])
            self.assertEqual(len(messages), 1)
            message = messages[0]
            self.assertEqual(message.tags, message_tag)
            self.assertEqual(message.message.strip(), expected_message.strip())

    def test_domain_overview_blocked_for_ineligible_user(self):
        """We could easily duplicate this test for all domain management
        views, but a single url test should be solid enough since all domain
        management pages share the same permissions class"""
        self.user.status = User.RESTRICTED
        self.user.save()
        home_page = self.app.get("/")
        self.assertContains(home_page, "igorville.gov")
        with less_console_noise():
            response = self.client.get(reverse("domain", kwargs={"pk": self.domain.id}))
            self.assertEqual(response.status_code, 403)


class TestDomainDNSSEC(TestDomainOverview):

    """MockEPPLib is already inherited."""

    def test_dnssec_page_refreshes_enable_button(self):
        """DNSSEC overview page loads when domain has no DNSSEC data
        and shows a 'Enable DNSSEC' button."""

        page = self.client.get(reverse("domain-dns-dnssec", kwargs={"pk": self.domain.id}))
        self.assertContains(page, "Enable DNSSEC")

    def test_dnssec_page_loads_with_data_in_domain(self):
        """DNSSEC overview page loads when domain has DNSSEC data
        and the template contains a button to disable DNSSEC."""

        page = self.client.get(reverse("domain-dns-dnssec", kwargs={"pk": self.domain_multdsdata.id}))
        self.assertContains(page, "Disable DNSSEC")

        # Prepare the data for the POST request
        post_data = {
            "disable_dnssec": "Disable DNSSEC",
        }
        updated_page = self.client.post(
            reverse("domain-dns-dnssec", kwargs={"pk": self.domain.id}),
            post_data,
            follow=True,
        )

        self.assertEqual(updated_page.status_code, 200)

        self.assertContains(updated_page, "Enable DNSSEC")

    def test_ds_form_loads_with_no_domain_data(self):
        """DNSSEC Add DS data page loads when there is no
        domain DNSSEC data and shows a button to Add new record"""

        page = self.client.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dnssec_none.id}))
        self.assertContains(page, "You have no DS data added")
        self.assertContains(page, "Add new record")

    def test_ds_form_loads_with_ds_data(self):
        """DNSSEC Add DS data page loads when there is
        domain DNSSEC DS data and shows the data"""

        page = self.client.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        self.assertContains(page, "DS data record 1")

    def test_ds_data_form_modal(self):
        """When user clicks on save, a modal pops up."""
        add_data_page = self.app.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        # Assert that a hidden trigger for the modal does not exist.
        # This hidden trigger will pop on the page when certain condition are met:
        # 1) Initial form contained DS data, 2) All data is deleted and form is
        # submitted.
        self.assertNotContains(add_data_page, "Trigger Disable DNSSEC Modal")
        # Simulate a delete all data
        form_data = {}
        response = self.client.post(
            reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}),
            data=form_data,
        )
        self.assertEqual(response.status_code, 200)  # Adjust status code as needed
        # Now check to see whether the JS trigger for the modal is present on the page
        self.assertContains(response, "Trigger Disable DNSSEC Modal")

    def test_ds_data_form_submits(self):
        """DS data form submits successfully

        Uses self.app WebTest because we need to interact with forms.
        """
        add_data_page = self.app.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        with less_console_noise():  # swallow log warning message
            result = add_data_page.forms[0].submit()
        # form submission was a post, response should be a redirect
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}),
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        page = result.follow()
        self.assertContains(page, "The DS data records for this domain have been updated.")

    def test_ds_data_form_invalid(self):
        """DS data form errors with invalid data (missing required fields)

        Uses self.app WebTest because we need to interact with forms.
        """
        add_data_page = self.app.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # all four form fields are required, so will test with each blank
        add_data_page.forms[0]["form-0-key_tag"] = ""
        add_data_page.forms[0]["form-0-algorithm"] = ""
        add_data_page.forms[0]["form-0-digest_type"] = ""
        add_data_page.forms[0]["form-0-digest"] = ""
        with less_console_noise():  # swallow logged warning message
            result = add_data_page.forms[0].submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the field.
        self.assertContains(result, "Key tag is required", count=2, status_code=200)
        self.assertContains(result, "Algorithm is required", count=2, status_code=200)
        self.assertContains(result, "Digest type is required", count=2, status_code=200)
        self.assertContains(result, "Digest is required", count=2, status_code=200)

    def test_ds_data_form_invalid_keytag(self):
        """DS data form errors with invalid data (key tag too large)

        Uses self.app WebTest because we need to interact with forms.
        """
        add_data_page = self.app.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # first two nameservers are required, so if we empty one out we should
        # get a form error
        add_data_page.forms[0]["form-0-key_tag"] = "65536"  # > 65535
        add_data_page.forms[0]["form-0-algorithm"] = ""
        add_data_page.forms[0]["form-0-digest_type"] = ""
        add_data_page.forms[0]["form-0-digest"] = ""
        with less_console_noise():  # swallow logged warning message
            result = add_data_page.forms[0].submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the field.
        self.assertContains(
            result, str(DsDataError(code=DsDataErrorCodes.INVALID_KEYTAG_SIZE)), count=2, status_code=200
        )

    def test_ds_data_form_invalid_digest_chars(self):
        """DS data form errors with invalid data (digest contains non hexadecimal chars)

        Uses self.app WebTest because we need to interact with forms.
        """
        add_data_page = self.app.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # first two nameservers are required, so if we empty one out we should
        # get a form error
        add_data_page.forms[0]["form-0-key_tag"] = "1234"
        add_data_page.forms[0]["form-0-algorithm"] = "3"
        add_data_page.forms[0]["form-0-digest_type"] = "1"
        add_data_page.forms[0]["form-0-digest"] = "GG1234"
        with less_console_noise():  # swallow logged warning message
            result = add_data_page.forms[0].submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the field.
        self.assertContains(
            result, str(DsDataError(code=DsDataErrorCodes.INVALID_DIGEST_CHARS)), count=2, status_code=200
        )

    def test_ds_data_form_invalid_digest_sha1(self):
        """DS data form errors with invalid data (digest is invalid sha-1)

        Uses self.app WebTest because we need to interact with forms.
        """
        add_data_page = self.app.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # first two nameservers are required, so if we empty one out we should
        # get a form error
        add_data_page.forms[0]["form-0-key_tag"] = "1234"
        add_data_page.forms[0]["form-0-algorithm"] = "3"
        add_data_page.forms[0]["form-0-digest_type"] = "1"  # SHA-1
        add_data_page.forms[0]["form-0-digest"] = "A123"
        with less_console_noise():  # swallow logged warning message
            result = add_data_page.forms[0].submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the field.
        self.assertContains(
            result, str(DsDataError(code=DsDataErrorCodes.INVALID_DIGEST_SHA1)), count=2, status_code=200
        )

    def test_ds_data_form_invalid_digest_sha256(self):
        """DS data form errors with invalid data (digest is invalid sha-256)

        Uses self.app WebTest because we need to interact with forms.
        """
        add_data_page = self.app.get(reverse("domain-dns-dnssec-dsdata", kwargs={"pk": self.domain_dsdata.id}))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # first two nameservers are required, so if we empty one out we should
        # get a form error
        add_data_page.forms[0]["form-0-key_tag"] = "1234"
        add_data_page.forms[0]["form-0-algorithm"] = "3"
        add_data_page.forms[0]["form-0-digest_type"] = "2"  # SHA-256
        add_data_page.forms[0]["form-0-digest"] = "GG1234"
        with less_console_noise():  # swallow logged warning message
            result = add_data_page.forms[0].submit()
        # form submission was a post with an error, response should be a 200
        # error text appears twice, once at the top of the page, once around
        # the field.
        self.assertContains(
            result, str(DsDataError(code=DsDataErrorCodes.INVALID_DIGEST_SHA256)), count=2, status_code=200
        )


class TestApplicationStatus(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.client.force_login(self.user)

    def test_application_status(self):
        """Checking application status page"""
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")

    def test_application_status_with_ineligible_user(self):
        """Checking application status page whith a blocked user.
        The user should still have access to view."""
        self.user.status = "ineligible"
        self.user.save()

        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")

    def test_application_withdraw(self):
        """Checking application status page"""
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")
        # click the "Withdraw request" button
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                withdraw_page = detail_page.click("Withdraw request")
                self.assertContains(withdraw_page, "Withdraw request for")
                home_page = withdraw_page.click("Withdraw request")
        # confirm that it has redirected, and the status has been updated to withdrawn
        self.assertRedirects(
            home_page,
            "/",
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=True,
        )
        home_page = self.app.get("/")
        self.assertContains(home_page, "Withdrawn")

    def test_application_withdraw_no_permissions(self):
        """Can't withdraw applications as a restricted user."""
        self.user.status = User.RESTRICTED
        self.user.save()
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")
        # Restricted user trying to withdraw results in 403 error
        with less_console_noise():
            for url_name in [
                "application-withdraw-confirmation",
                "application-withdrawn",
            ]:
                with self.subTest(url_name=url_name):
                    page = self.client.get(reverse(url_name, kwargs={"pk": application.pk}))
                    self.assertEqual(page.status_code, 403)

    def test_application_status_no_permissions(self):
        """Can't access applications without being the creator."""
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        other_user = User()
        other_user.save()
        application.creator = other_user
        application.save()

        # PermissionDeniedErrors make lots of noise in test output
        with less_console_noise():
            for url_name in [
                "application-status",
                "application-withdraw-confirmation",
                "application-withdrawn",
            ]:
                with self.subTest(url_name=url_name):
                    page = self.client.get(reverse(url_name, kwargs={"pk": application.pk}))
                    self.assertEqual(page.status_code, 403)

    def test_approved_application_not_in_active_requests(self):
        """An approved application is not shown in the Active
        Requests table on home.html."""
        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        # This works in our test environment because creating
        # an approved application here does not generate a
        # domain object, so we do not expect to see 'city.gov'
        # in either the Domains or Requests tables.
        self.assertNotContains(home_page, "city.gov")
