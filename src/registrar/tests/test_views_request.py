from unittest import skip
from unittest.mock import Mock, patch
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from api.tests.common import less_console_noise_decorator
from registrar.utility.constants import BranchChoices
from .common import MockSESClient, completed_domain_request, form_with_field  # type: ignore
from django_webtest import WebTest  # type: ignore
import boto3_mocking  # type: ignore

from registrar.models import (
    DomainRequest,
    DraftDomain,
    Domain,
    DomainInformation,
    Contact,
    User,
    Website,
    FederalAgency,
    Portfolio,
    UserPortfolioPermission,
)
from registrar.views.domain_request import DomainRequestWizard, Step

from .common import less_console_noise
from .test_views import TestWithUser
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices, UserPortfolioPermissionChoices
import logging

logger = logging.getLogger(__name__)


class DomainRequestTests(TestWithUser, WebTest):
    """Webtests for domain request to test filling and submitting."""

    # Doesn't work with CSRF checking
    # hypothesis is that CSRF_USE_SESSIONS is incompatible with WebTest
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.federal_agency, _ = FederalAgency.objects.get_or_create(agency="General Services Administration")
        self.app.set_user(self.user.username)
        self.TITLES = DomainRequestWizard.REGULAR_TITLES

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        Portfolio.objects.all().delete()
        User.objects.all().delete()
        FederalAgency.objects.all().delete()

    @less_console_noise_decorator
    def test_domain_request_form_intro_acknowledgement(self):
        """Tests that user is presented with intro acknowledgement page"""
        intro_page = self.app.get(reverse("domain-request:start"))
        self.assertContains(intro_page, "You’re about to start your .gov domain request")

    @less_console_noise_decorator
    def test_template_status_display(self):
        """Tests the display of status-related information in the template."""
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.user)
        domain_request.last_submitted_date = datetime.now()
        domain_request.save()
        response = self.app.get(f"/domain-request/{domain_request.id}")
        self.assertContains(response, "Submitted on:")
        self.assertContains(response, domain_request.last_submitted_date.strftime("%B %-d, %Y"))

    @patch.object(DomainRequest, "get_first_status_set_date")
    def test_get_first_status_started_date(self, mock_get_first_status_set_date):
        """Tests retrieval of the first date the status was set to 'started'."""

        # Set the mock to return a fixed date
        fixed_date = timezone.datetime(2023, 1, 1).date()
        mock_get_first_status_set_date.return_value = fixed_date

        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.STARTED, user=self.user)
        domain_request.last_status_update = None
        domain_request.save()

        response = self.app.get(f"/domain-request/{domain_request.id}")
        # Ensure that the date is still set to None
        self.assertIsNone(domain_request.last_status_update)
        # We should still grab a date for this field in this event - but it should come from the audit log instead
        self.assertContains(response, "Started on:")
        self.assertContains(response, fixed_date.strftime("%B %-d, %Y"))

        # If a status date is set, we display that instead
        domain_request.last_status_update = datetime.now()
        domain_request.save()

        response = self.app.get(f"/domain-request/{domain_request.id}")

        # We should still grab a date for this field in this event - but it should come from the audit log instead
        self.assertContains(response, "Started on:")
        self.assertContains(response, domain_request.last_status_update.strftime("%B %-d, %Y"))

    @less_console_noise_decorator
    def test_domain_request_form_intro_is_skipped_when_edit_access(self):
        """Tests that user is NOT presented with intro acknowledgement page when accessed through 'edit'"""
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.STARTED, user=self.user)
        detail_page = self.app.get(f"/domain-request/{domain_request.id}/edit/")
        # Check that the response is a redirect
        self.assertEqual(detail_page.status_code, 302)
        # You can access the 'Location' header to get the redirect URL
        redirect_url = detail_page.url
        self.assertEqual(redirect_url, f"/request/{domain_request.id}/generic_org_type/")

    @less_console_noise_decorator
    def test_domain_request_form_empty_submit(self):
        """Tests empty submit on the first page after the acknowledgement page"""
        intro_page = self.app.get(reverse("domain-request:start"))
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

    @less_console_noise_decorator
    def test_domain_request_multiple_domain_requests_exist(self):
        """Test that an info message appears when user has multiple domain requests already"""
        # create and submit a domain request
        domain_request = completed_domain_request(user=self.user)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            domain_request.submit()
            domain_request.save()

        # now, attempt to create another one
        intro_page = self.app.get(reverse("domain-request:start"))
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
    @less_console_noise_decorator
    def test_domain_request_form_submission(self):
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

        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = "federal"
        # test next button and validate data
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # should see results in db
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.generic_org_type, "federal")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], f"/request/{domain_request.id}/organization_federal/")
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.federal_type, "executive")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(federal_result.status_code, 302)
        self.assertEqual(federal_result["Location"], f"/request/{domain_request.id}/organization_contact/")
        num_pages_tested += 1

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        org_contact_form["organization_contact-federal_agency"] = self.federal_agency.id
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.organization_name, "Testorg")
        self.assertEqual(domain_request.address_line1, "address 1")
        self.assertEqual(domain_request.address_line2, "address 2")
        self.assertEqual(domain_request.city, "NYC")
        self.assertEqual(domain_request.state_territory, "NY")
        self.assertEqual(domain_request.zipcode, "10002")
        self.assertEqual(domain_request.urbanization, "URB Royal Oaks")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(org_contact_result.status_code, 302)
        self.assertEqual(org_contact_result["Location"], f"/request/{domain_request.id}/senior_official/")
        num_pages_tested += 1

        # ---- SENIOR OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_page = org_contact_result.follow()
        so_form = so_page.forms[0]
        so_form["senior_official-first_name"] = "Testy ATO"
        so_form["senior_official-last_name"] = "Tester ATO"
        so_form["senior_official-title"] = "Chief Tester"
        so_form["senior_official-email"] = "testy@town.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_result = so_form.submit()
        # validate that data from this step are being saved
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.senior_official.first_name, "Testy ATO")
        self.assertEqual(domain_request.senior_official.last_name, "Tester ATO")
        self.assertEqual(domain_request.senior_official.title, "Chief Tester")
        self.assertEqual(domain_request.senior_official.email, "testy@town.com")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(so_result.status_code, 302)
        self.assertEqual(so_result["Location"], f"/request/{domain_request.id}/current_sites/")
        num_pages_tested += 1

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = so_result.follow()
        current_sites_form = current_sites_page.forms[0]
        current_sites_form["current_sites-0-website"] = "www.city.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()
        # validate that data from this step are being saved
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(
            domain_request.current_websites.filter(website="http://www.city.com").count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(current_sites_result.status_code, 302)
        self.assertEqual(current_sites_result["Location"], f"/request/{domain_request.id}/dotgov_domain/")
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.requested_domain.name, "city.gov")
        self.assertEqual(domain_request.alternative_domains.filter(website="city1.gov").count(), 1)
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(dotgov_result.status_code, 302)
        self.assertEqual(dotgov_result["Location"], f"/request/{domain_request.id}/purpose/")
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.purpose, "For all kinds of things.")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(purpose_result.status_code, 302)
        self.assertEqual(purpose_result["Location"], f"/request/{domain_request.id}/other_contacts/")
        num_pages_tested += 1

        # ---- OTHER CONTACTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_page = purpose_result.follow()

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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(
            domain_request.other_contacts.filter(
                first_name="Testy2",
                last_name="Tester2",
                title="Another Tester",
                email="testy2@town.com",
                phone="(201) 555 5557",
            ).count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(other_contacts_result.status_code, 302)
        self.assertEqual(other_contacts_result["Location"], f"/request/{domain_request.id}/additional_details/")
        num_pages_tested += 1

        # ---- ADDITIONAL DETAILS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        additional_details_page = other_contacts_result.follow()
        additional_details_form = additional_details_page.forms[0]

        # load inputs with test data

        additional_details_form["additional_details-has_cisa_representative"] = "True"
        additional_details_form["additional_details-has_anything_else_text"] = "True"
        additional_details_form["additional_details-cisa_representative_first_name"] = "CISA-first-name"
        additional_details_form["additional_details-cisa_representative_last_name"] = "CISA-last-name"
        additional_details_form["additional_details-cisa_representative_email"] = "FakeEmail@gmail.com"
        additional_details_form["additional_details-anything_else"] = "Nothing else."

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        additional_details_result = additional_details_form.submit()
        # validate that data from this step are being saved
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.cisa_representative_first_name, "CISA-first-name")
        self.assertEqual(domain_request.cisa_representative_last_name, "CISA-last-name")
        self.assertEqual(domain_request.cisa_representative_email, "FakeEmail@gmail.com")
        self.assertEqual(domain_request.anything_else, "Nothing else.")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(additional_details_result.status_code, 302)
        self.assertEqual(additional_details_result["Location"], f"/request/{domain_request.id}/requirements/")
        num_pages_tested += 1

        # ---- REQUIREMENTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_page = additional_details_result.follow()
        requirements_form = requirements_page.forms[0]

        requirements_form["requirements-is_policy_acknowledged"] = True

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_result = requirements_form.submit()
        # validate that data from this step are being saved
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.is_policy_acknowledged, True)
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(requirements_result.status_code, 302)
        self.assertEqual(requirements_result["Location"], f"/request/{domain_request.id}/review/")
        num_pages_tested += 1

        # ---- REVIEW AND FINSIHED PAGES  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        review_page = requirements_result.follow()
        review_form = review_page.forms[0]

        # Review page contains all the previously entered data
        # Let's make sure the long org name is displayed
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
        self.assertContains(review_page, "city.com")
        self.assertContains(review_page, "city.gov")
        self.assertContains(review_page, "city1.gov")
        self.assertContains(review_page, "For all kinds of things.")
        self.assertContains(review_page, "Testy2")
        self.assertContains(review_page, "Tester2")
        self.assertContains(review_page, "Another Tester")
        self.assertContains(review_page, "testy2@town.com")
        self.assertContains(review_page, "(201) 555-5557")
        self.assertContains(review_page, "FakeEmail@gmail.com")
        self.assertContains(review_page, "Nothing else.")

        # We can't test the modal itself as it relies on JS for init and triggering,
        # but we can test for the existence of its trigger:
        self.assertContains(review_page, "toggle-submit-domain-request")
        # And the existence of the modal's data parked and ready for the js init.
        # The next assert also tests for the passed requested domain context from
        # the view > domain_request_form > modal
        self.assertContains(review_page, "You are about to submit a domain request for")
        self.assertContains(review_page, "city.gov")

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

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_domain_request_form_submission_incomplete(self):
        num_pages_tested = 0
        # skipping elections, type_of_work, tribal_government

        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = "federal"
        # test next button and validate data
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # should see results in db
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.generic_org_type, "federal")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], f"/request/{domain_request.id}/organization_federal/")
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.federal_type, "executive")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(federal_result.status_code, 302)
        self.assertEqual(federal_result["Location"], f"/request/{domain_request.id}/organization_contact/")
        num_pages_tested += 1

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        org_contact_form["organization_contact-federal_agency"] = self.federal_agency.id
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.organization_name, "Testorg")
        self.assertEqual(domain_request.address_line1, "address 1")
        self.assertEqual(domain_request.address_line2, "address 2")
        self.assertEqual(domain_request.city, "NYC")
        self.assertEqual(domain_request.state_territory, "NY")
        self.assertEqual(domain_request.zipcode, "10002")
        self.assertEqual(domain_request.urbanization, "URB Royal Oaks")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(org_contact_result.status_code, 302)
        self.assertEqual(org_contact_result["Location"], f"/request/{domain_request.id}/senior_official/")
        num_pages_tested += 1

        # ---- SENIOR OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_page = org_contact_result.follow()
        so_form = so_page.forms[0]
        so_form["senior_official-first_name"] = "Testy ATO"
        so_form["senior_official-last_name"] = "Tester ATO"
        so_form["senior_official-title"] = "Chief Tester"
        so_form["senior_official-email"] = "testy@town.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_result = so_form.submit()
        # validate that data from this step are being saved
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.senior_official.first_name, "Testy ATO")
        self.assertEqual(domain_request.senior_official.last_name, "Tester ATO")
        self.assertEqual(domain_request.senior_official.title, "Chief Tester")
        self.assertEqual(domain_request.senior_official.email, "testy@town.com")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(so_result.status_code, 302)
        self.assertEqual(so_result["Location"], f"/request/{domain_request.id}/current_sites/")
        num_pages_tested += 1

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = so_result.follow()
        current_sites_form = current_sites_page.forms[0]
        current_sites_form["current_sites-0-website"] = "www.city.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()
        # validate that data from this step are being saved
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(
            domain_request.current_websites.filter(website="http://www.city.com").count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(current_sites_result.status_code, 302)
        self.assertEqual(current_sites_result["Location"], f"/request/{domain_request.id}/dotgov_domain/")
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.requested_domain.name, "city.gov")
        self.assertEqual(domain_request.alternative_domains.filter(website="city1.gov").count(), 1)
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(dotgov_result.status_code, 302)
        self.assertEqual(dotgov_result["Location"], f"/request/{domain_request.id}/purpose/")
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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.purpose, "For all kinds of things.")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(purpose_result.status_code, 302)
        self.assertEqual(purpose_result["Location"], f"/request/{domain_request.id}/other_contacts/")
        num_pages_tested += 1

        # ---- OTHER CONTACTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_page = purpose_result.follow()

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
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(
            domain_request.other_contacts.filter(
                first_name="Testy2",
                last_name="Tester2",
                title="Another Tester",
                email="testy2@town.com",
                phone="(201) 555 5557",
            ).count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(other_contacts_result.status_code, 302)
        self.assertEqual(other_contacts_result["Location"], f"/request/{domain_request.id}/additional_details/")
        num_pages_tested += 1

        # ---- ADDITIONAL DETAILS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        additional_details_page = other_contacts_result.follow()
        additional_details_form = additional_details_page.forms[0]

        # load inputs with test data

        additional_details_form["additional_details-has_cisa_representative"] = "True"
        additional_details_form["additional_details-has_anything_else_text"] = "True"
        additional_details_form["additional_details-cisa_representative_first_name"] = "cisa-first-name"
        additional_details_form["additional_details-cisa_representative_last_name"] = "cisa-last-name"
        additional_details_form["additional_details-cisa_representative_email"] = "FakeEmail@gmail.com"
        additional_details_form["additional_details-anything_else"] = "Nothing else."

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        additional_details_result = additional_details_form.submit()
        # validate that data from this step are being saved
        domain_request = DomainRequest.objects.get()  # there's only one
        self.assertEqual(domain_request.cisa_representative_first_name, "cisa-first-name")
        self.assertEqual(domain_request.cisa_representative_last_name, "cisa-last-name")
        self.assertEqual(domain_request.cisa_representative_email, "FakeEmail@gmail.com")
        self.assertEqual(domain_request.anything_else, "Nothing else.")
        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(additional_details_result.status_code, 302)
        self.assertEqual(additional_details_result["Location"], f"/request/{domain_request.id}/requirements/")
        num_pages_tested += 1

        # ---- REQUIREMENTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_page = additional_details_result.follow()
        requirements_form = requirements_page.forms[0]

        # Before we go to the review page, let's remove some of the data from the request:
        domain_request = DomainRequest.objects.get()  # there's only one

        domain_request.generic_org_type = None
        domain_request.save()

        # Refresh the Requirements page so snapshot matches the new updated_at
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_page = self.app.get(reverse("domain-request:requirements", args=[domain_request.id]))
        requirements_form = requirements_page.forms[0]
        requirements_form["requirements-is_policy_acknowledged"] = True

        # Submit and test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_result = requirements_form.submit()
        # validate that data from this step are being saved
        domain_request.refresh_from_db()
        self.assertEqual(domain_request.is_policy_acknowledged, True)

        # the post request should return a redirect to the next form in
        # the domain request page
        self.assertEqual(requirements_result.status_code, 302)
        self.assertEqual(requirements_result["Location"], f"/request/{domain_request.id}/review/")
        num_pages_tested += 1

        # ---- REVIEW AND FINSIHED PAGES  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        review_page = requirements_result.follow()
        # review_form = review_page.forms[0]

        # Review page contains all the previously entered data
        # Let's make sure the long org name is displayed
        self.assertNotContains(review_page, "Federal")
        # self.assertContains(review_page, "Executive")
        self.assertContains(review_page, "Incomplete", count=1)

        # We can't test the modal itself as it relies on JS for init and triggering,
        # but we can test for the existence of its trigger:
        self.assertContains(review_page, "toggle-submit-domain-request")
        # And the existence of the modal's data parked and ready for the js init.
        # The next assert also tests for the passed requested domain context from
        # the view > domain_request_form > modal
        self.assertNotContains(review_page, "You are about to submit a domain request for city.gov")
        self.assertContains(review_page, "Your request form is incomplete")

    # This is the start of a test to check an existing domain_request, it currently
    # does not work and results in errors as noted in:
    # https://github.com/cisagov/getgov/pull/728
    @skip("WIP")
    def test_domain_request_form_started_allsteps(self):
        num_pages_tested = 0
        # elections, type_of_work, tribal_government
        SKIPPED_PAGES = 3
        DASHBOARD_PAGE = 1
        num_pages = len(self.TITLES) - SKIPPED_PAGES + DASHBOARD_PAGE

        domain_request = completed_domain_request(user=self.user)
        domain_request.save()
        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        self.assertContains(home_page, "Started")
        num_pages_tested += 1

        # TODO: For some reason this click results in a new domain request being generated
        # This appraoch is an alternatie to using get as is being done below
        #
        # type_page = home_page.click("Edit")

        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        url = reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk})
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # TODO: The following line results in a django error on middleware
        response = self.client.get(url, follow=True)
        self.assertContains(response, "Type of organization")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # TODO: Step through the remaining pages

        self.assertEqual(num_pages, num_pages_tested)

    @less_console_noise_decorator
    def test_domain_request_form_conditional_federal(self):
        """Federal branch question is shown for federal organizations."""
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = "federal"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the federal branch
        # question
        self.assertEqual(type_result.status_code, 302)
        self.assertIn("organization_federal", type_result["Location"])

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
        self.assertIn("organization_federal", type_result["Location"])
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = federal_result.follow()
        self.assertContains(contact_page, "Federal agency")

    @less_console_noise_decorator
    def test_domain_request_form_conditional_elections(self):
        """Election question is shown for other organizations."""
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = "county"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the elections question
        self.assertEqual(type_result.status_code, 302)
        self.assertIn("organization_election", type_result["Location"])

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
        self.assertIn("organization_contact", election_result["Location"])
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = election_result.follow()
        self.assertNotContains(contact_page, "Federal agency")

    @less_console_noise_decorator
    def test_domain_request_form_section_skipping(self):
        """Can skip forward and back in sections"""
        DomainRequest.objects.all().delete()
        intro_page = self.app.get(reverse("domain-request:start"))
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

        # fill out the organization type section then submit
        type_form = type_page.forms[0]
        type_form["generic_org_type-generic_org_type"] = "federal"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # follow first redirect to the next section
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()

        # we need to fill out the federal section so it stays unlocked
        fed_branch_form = federal_page.forms[0]
        fed_branch_form["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        fed_branch_form.submit()

        # Now click back to the organization type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        new_page = federal_page.click(str(self.TITLES["generic_org_type"]), index=0)
        # Should be a link to the organization_federal page since it is now unlocked
        all_domain_requests = DomainRequest.objects.all()
        self.assertEqual(all_domain_requests.count(), 1)

        new_request_id = all_domain_requests.first().id
        self.assertGreater(
            len(new_page.html.find_all("a", href=f"/request/{new_request_id}/organization_federal/")),
            0,
        )

    @less_console_noise_decorator
    def test_domain_request_form_nonfederal(self):
        """Non-federal organizations don't have to provide their federal agency."""
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = DomainRequest.OrganizationChoices.INTERSTATE
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
        self.assertIn("about_your_organization", contact_result["Location"])

    @less_console_noise_decorator
    def test_domain_request_about_your_organization_special(self):
        """Special districts have to answer an additional question."""
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = DomainRequest.OrganizationChoices.SPECIAL_DISTRICT
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.forms[0].submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.ABOUT_YOUR_ORGANIZATION])

    @less_console_noise_decorator
    def test_federal_agency_dropdown_excludes_expected_values(self):
        """The Federal Agency dropdown on a domain request form should not
        include options for gov Administration and Non-Federal Agency"""
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = "federal"

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

        # gov Administration and Non-Federal Agency should not be federal agency options
        self.assertNotContains(org_contact_page, "gov Administration")
        self.assertNotContains(org_contact_page, "Non-Federal Agency")
        # make sure correct federal agency options still show up
        self.assertContains(org_contact_page, "General Services Administration")

    @less_console_noise_decorator
    def test_yes_no_contact_form_inits_blank_for_new_domain_request(self):
        """On the Other Contacts page, the yes/no form gets initialized with nothing selected for
        new domain requests"""
        other_contacts_page = self.app.get(reverse("domain-request:other_contacts", kwargs={"domain_request_pk": 0}))
        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, None)

    @less_console_noise_decorator
    def test_yes_no_additional_form_inits_blank_for_new_domain_request(self):
        """On the Additional Details page, the yes/no form gets initialized with nothing selected for
        new domain requests"""
        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": 0})
        )
        additional_form = additional_details_page.forms[0]

        # Check the cisa representative yes/no field
        self.assertEquals(additional_form["additional_details-has_cisa_representative"].value, None)

        # Check the anything else yes/no field
        self.assertEquals(additional_form["additional_details-has_anything_else_text"].value, None)

    @less_console_noise_decorator
    def test_yes_no_form_inits_yes_for_domain_request_with_other_contacts(self):
        """On the Other Contacts page, the yes/no form gets initialized with YES selected if the
        domain request has other contacts"""
        # Domain Request has other contacts by default
        domain_request = completed_domain_request(user=self.user)
        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

    @less_console_noise_decorator
    def test_yes_no_form_inits_yes_for_cisa_representative_and_anything_else(self):
        """On the Additional Details page, the yes/no form gets initialized with YES selected
        for both yes/no radios if the domain request has a values for cisa_representative_first_name and
        anything_else"""

        domain_request = completed_domain_request(user=self.user, has_anything_else=True, has_cisa_representative=True)
        domain_request.anything_else = "1234"
        domain_request.save()

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_form = additional_details_page.forms[0]

        # Check the cisa representative yes/no field
        yes_no_cisa = additional_details_form["additional_details-has_cisa_representative"].value
        self.assertEquals(yes_no_cisa, "True")

        # Check the anything else yes/no field
        yes_no_anything_else = additional_details_form["additional_details-has_anything_else_text"].value
        self.assertEquals(yes_no_anything_else, "True")

    @less_console_noise_decorator
    def test_yes_no_form_inits_no_for_domain_request_with_no_other_contacts_rationale(self):
        """On the Other Contacts page, the yes/no form gets initialized with NO selected if the
        domain request has no other contacts"""
        # Domain request has other contacts by default
        domain_request = completed_domain_request(user=self.user, has_other_contacts=False)
        domain_request.no_other_contacts_rationale = "Hello!"
        domain_request.save()
        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "False")

    @less_console_noise_decorator
    def test_yes_no_form_for_domain_request_with_no_cisa_representative_and_anything_else(self):
        """On the Additional details page, the form preselects "no" when has_cisa_representative
        and anything_else is no"""

        domain_request = completed_domain_request(
            user=self.user, has_anything_else=False, has_cisa_representative=False
        )

        # Unlike the other contacts form, the no button is tracked with these boolean fields.
        # This means that we should expect this to correlate with the no button.
        domain_request.has_anything_else_text = False
        domain_request.save()

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_form = additional_details_page.forms[0]

        # Check the cisa representative yes/no field
        yes_no_cisa = additional_details_form["additional_details-has_cisa_representative"].value
        self.assertEquals(yes_no_cisa, None)

        # Check the anything else yes/no field
        yes_no_anything_else = additional_details_form["additional_details-has_anything_else_text"].value
        self.assertEquals(yes_no_anything_else, "False")

    @less_console_noise_decorator
    def test_submitting_additional_details_deletes_cisa_representative_and_anything_else(self):
        """When a user submits the Additional Details form with no selected for all fields,
        the domain request's data gets wiped when submitted"""
        domain_request = completed_domain_request(name="nocisareps.gov", user=self.user)
        domain_request.cisa_representative_first_name = "cisa-firstname1"
        domain_request.cisa_representative_last_name = "cisa-lastname1"
        domain_request.cisa_representative_email = "fake@faketown.gov"
        domain_request.save()

        # Make sure we have the data we need for the test
        self.assertEqual(domain_request.anything_else, "There is more")
        self.assertEqual(domain_request.cisa_representative_first_name, "cisa-firstname1")
        self.assertEqual(domain_request.cisa_representative_last_name, "cisa-lastname1")
        self.assertEqual(domain_request.cisa_representative_email, "fake@faketown.gov")

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_form = additional_details_page.forms[0]

        # Check the cisa representative yes/no field
        yes_no_cisa = additional_details_form["additional_details-has_cisa_representative"].value
        self.assertEquals(yes_no_cisa, "True")

        # Check the anything else yes/no field
        yes_no_anything_else = additional_details_form["additional_details-has_anything_else_text"].value
        self.assertEquals(yes_no_anything_else, "True")

        # Set fields to false
        additional_details_form["additional_details-has_cisa_representative"] = "False"
        additional_details_form["additional_details-has_anything_else_text"] = "False"

        # Submit the form
        additional_details_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the anything_else and cisa_representative information have been deleted from the DB
        domain_request = DomainRequest.objects.get(requested_domain__name="nocisareps.gov")

        # Check that our data has been cleared
        self.assertEqual(domain_request.anything_else, None)
        self.assertEqual(domain_request.cisa_representative_first_name, None)
        self.assertEqual(domain_request.cisa_representative_last_name, None)
        self.assertEqual(domain_request.cisa_representative_email, None)

        # Double check the yes/no fields
        self.assertEqual(domain_request.has_anything_else_text, False)
        self.assertEqual(domain_request.cisa_representative_first_name, None)
        self.assertEqual(domain_request.cisa_representative_last_name, None)
        self.assertEqual(domain_request.cisa_representative_email, None)

    @less_console_noise_decorator
    def test_submitting_additional_details_populates_cisa_representative_and_anything_else(self):
        """When a user submits the Additional Details form,
        the domain request's data gets submitted"""
        domain_request = completed_domain_request(
            name="cisareps.gov", user=self.user, has_anything_else=False, has_cisa_representative=False
        )

        # Make sure we have the data we need for the test
        self.assertEqual(domain_request.anything_else, None)
        self.assertEqual(domain_request.cisa_representative_first_name, None)

        # These fields should not be selected at all, since we haven't initialized the form yet
        self.assertEqual(domain_request.has_anything_else_text, None)
        self.assertEqual(domain_request.has_cisa_representative, None)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_form = additional_details_page.forms[0]

        # Set fields to true, and set data on those fields
        additional_details_form["additional_details-has_cisa_representative"] = "True"
        additional_details_form["additional_details-has_anything_else_text"] = "True"
        additional_details_form["additional_details-cisa_representative_first_name"] = "cisa-firstname"
        additional_details_form["additional_details-cisa_representative_last_name"] = "cisa-lastname"
        additional_details_form["additional_details-cisa_representative_email"] = "test@faketest.gov"
        additional_details_form["additional_details-anything_else"] = "redandblue"

        # Submit the form
        additional_details_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the anything_else and cisa_representative information exist in the db
        domain_request = DomainRequest.objects.get(requested_domain__name="cisareps.gov")

        self.assertEqual(domain_request.anything_else, "redandblue")
        self.assertEqual(domain_request.cisa_representative_first_name, "cisa-firstname")
        self.assertEqual(domain_request.cisa_representative_last_name, "cisa-lastname")
        self.assertEqual(domain_request.cisa_representative_email, "test@faketest.gov")

        self.assertEqual(domain_request.has_cisa_representative, True)
        self.assertEqual(domain_request.has_anything_else_text, True)

    @less_console_noise_decorator
    def test_if_cisa_representative_yes_no_form_is_yes_then_field_is_required(self):
        """Applicants with a cisa representative must provide a value"""
        domain_request = completed_domain_request(
            name="cisareps.gov", user=self.user, has_anything_else=False, has_cisa_representative=False
        )

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_form = additional_details_page.forms[0]

        # Set fields to true, and set data on those fields
        additional_details_form["additional_details-has_cisa_representative"] = "True"
        additional_details_form["additional_details-has_anything_else_text"] = "False"

        # Submit the form
        response = additional_details_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        self.assertContains(response, "Enter the first name / given name of the CISA regional representative.")
        self.assertContains(response, "Enter the last name / family name of the CISA regional representative.")

    @less_console_noise_decorator
    def test_if_anything_else_yes_no_form_is_yes_then_field_is_required(self):
        """Applicants with a anything else must provide a value"""
        domain_request = completed_domain_request(name="cisareps.gov", user=self.user, has_anything_else=False)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_form = additional_details_page.forms[0]

        # Set fields to true, and set data on those fields
        additional_details_form["additional_details-has_cisa_representative"] = "False"
        additional_details_form["additional_details-has_anything_else_text"] = "True"

        # Submit the form
        response = additional_details_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        expected_message = "Provide additional details you’d like us to know. If you have nothing to add, select “No.”"
        self.assertContains(response, expected_message)

    @less_console_noise_decorator
    def test_additional_details_form_fields_required(self):
        """When a user submits the Additional Details form without checking the
        has_cisa_representative and has_anything_else_text fields, the form should deny this action"""
        domain_request = completed_domain_request(
            name="cisareps.gov", user=self.user, has_anything_else=False, has_cisa_representative=False
        )

        self.assertEqual(domain_request.has_anything_else_text, None)
        self.assertEqual(domain_request.has_cisa_representative, None)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_page = self.app.get(
            reverse("domain-request:additional_details", kwargs={"domain_request_pk": domain_request.id})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        additional_details_form = additional_details_page.forms[0]

        # Submit the form
        response = additional_details_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # We expect to see this twice for both fields. This results in a count of 4
        # due to screen reader information / html.
        self.assertContains(response, "This question is required.", count=4)

    @less_console_noise_decorator
    def test_submitting_other_contacts_deletes_no_other_contacts_rationale(self):
        """When a user submits the Other Contacts form with other contacts selected, the domain request's
        no other contacts rationale gets deleted"""
        # Domain request has other contacts by default
        domain_request = completed_domain_request(user=self.user, has_other_contacts=False)
        domain_request.no_other_contacts_rationale = "Hello!"
        domain_request.save()
        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.pk})
        )
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
        domain_request = DomainRequest.objects.get()
        self.assertEqual(
            domain_request.other_contacts.count(),
            1,
        )

        self.assertEquals(
            domain_request.no_other_contacts_rationale,
            None,
        )

    @less_console_noise_decorator
    def test_submitting_no_other_contacts_rationale_deletes_other_contacts(self):
        """When a user submits the Other Contacts form with no other contacts selected, the domain request's
        other contacts get deleted for other contacts that exist and are not joined to other objects
        """
        # Domain request has other contacts by default
        domain_request = completed_domain_request(user=self.user)
        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

        other_contacts_form["other_contacts-has_other_contacts"] = "False"

        other_contacts_form["other_contacts-no_other_contacts_rationale"] = "Hello again!"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier has been removed from the database
        domain_request = DomainRequest.objects.get()
        self.assertEqual(
            domain_request.other_contacts.count(),
            0,
        )

        self.assertEquals(
            domain_request.no_other_contacts_rationale,
            "Hello again!",
        )

    @less_console_noise_decorator
    def test_submitting_no_other_contacts_rationale_removes_reference_other_contacts_when_joined(self):
        """When a user submits the Other Contacts form with no other contacts selected, the domain request's
        other contacts references get removed for other contacts that exist and are joined to other objects"""
        # Populate the database with a domain request that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        so, _ = Contact.objects.get_or_create(
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
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )
        domain_request.other_contacts.add(other)

        # Now let's join the other contact to another object
        domain_info = DomainInformation.objects.create(requester=self.user)
        domain_info.other_contacts.set([other])

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

        other_contacts_form["other_contacts-has_other_contacts"] = "False"

        other_contacts_form["other_contacts-no_other_contacts_rationale"] = "Hello again!"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier is no longer associated with the domain request
        domain_request = DomainRequest.objects.get()
        self.assertEqual(
            domain_request.other_contacts.count(),
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
            domain_request.no_other_contacts_rationale,
            "Hello again!",
        )

    @less_console_noise_decorator
    def test_if_yes_no_form_is_no_then_no_other_contacts_required(self):
        """Applicants with no other contacts have to give a reason."""
        other_contacts_page = self.app.get(reverse("domain-request:other_contacts", kwargs={"domain_request_pk": 0}))
        other_contacts_form = other_contacts_page.forms[0]
        other_contacts_form["other_contacts-has_other_contacts"] = "False"
        response = other_contacts_page.forms[0].submit()

        # The textarea for no other contacts returns this error message
        # Assert that it is returned, ie the no other contacts form is required
        self.assertContains(response, "Rationale for no other employees is required.")

        # The first name field for other contacts returns this error message
        # Assert that it is not returned, ie the contacts form is not required
        self.assertNotContains(response, "Enter the first name / given name of this contact.")

    @less_console_noise_decorator
    def test_if_yes_no_form_is_yes_then_other_contacts_required(self):
        """Applicants with other contacts do not have to give a reason."""
        other_contacts_page = self.app.get(reverse("domain-request:other_contacts", kwargs={"domain_request_pk": 0}))
        other_contacts_form = other_contacts_page.forms[0]
        other_contacts_form["other_contacts-has_other_contacts"] = "True"
        response = other_contacts_page.forms[0].submit()

        # The textarea for no other contacts returns this error message
        # Assert that it is not returned, ie the no other contacts form is not required
        self.assertNotContains(response, "Rationale for no other employees is required.")

        # The first name field for other contacts returns this error message
        # Assert that it is returned, ie the contacts form is required
        self.assertContains(response, "Enter the first name / given name of this contact.")

    @less_console_noise_decorator
    def test_delete_other_contact(self):
        """Other contacts can be deleted after being saved to database.

        This formset uses the DJANGO DELETE widget. We'll test that by setting 2 contacts on a domain request,
        loading the form and marking one contact up for deletion."""
        # Populate the database with a domain request that
        # has 2 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        so, _ = Contact.objects.get_or_create(
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
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )
        domain_request.other_contacts.add(other)
        domain_request.other_contacts.add(other2)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.id})
        )
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
        domain_request = DomainRequest.objects.get()
        self.assertEqual(domain_request.other_contacts.count(), 1)
        self.assertEqual(domain_request.other_contacts.first().first_name, "Testy3")

    @less_console_noise_decorator
    def test_delete_other_contact_does_not_allow_zero_contacts(self):
        """Delete Other Contact does not allow submission with zero contacts."""
        # Populate the database with a domain request that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        so, _ = Contact.objects.get_or_create(
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
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )
        domain_request.other_contacts.add(other)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.id})
        )
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
        domain_request = DomainRequest.objects.get()
        self.assertEqual(domain_request.other_contacts.count(), 1)
        self.assertEqual(domain_request.other_contacts.first().first_name, "Testy2")

    @less_console_noise_decorator
    def test_delete_other_contact_sets_visible_empty_form_as_required_after_failed_submit(self):
        """When you:
            1. add an empty contact,
            2. delete existing contacts,
            3. then submit,
        The forms on page reload shows all the required fields and their errors."""

        # Populate the database with a domain request that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        so, _ = Contact.objects.get_or_create(
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
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )
        domain_request.other_contacts.add(other)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.id})
        )
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

    @less_console_noise_decorator
    def test_edit_other_contact_in_place(self):
        """When you:
            1. edit an existing contact which is not joined to another model,
            2. then submit,
        the domain request is linked to the existing contact, and the existing contact updated."""

        # Populate the database with a domain request that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch
        so, _ = Contact.objects.get_or_create(
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
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )
        domain_request.other_contacts.add(other)

        # other_contact_pk is the initial pk of the other contact. set it before update
        # to be able to verify after update that the same contact object is in place
        other_contact_pk = other.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")

        # update the first name of the contact
        other_contacts_form["other_contacts-0-first_name"] = "Testy3"

        # Submit the updated form
        other_contacts_form.submit()

        domain_request.refresh_from_db()

        # assert that the Other Contact is updated "in place"
        other_contact = domain_request.other_contacts.all()[0]
        self.assertEquals(other_contact_pk, other_contact.id)
        self.assertEquals("Testy3", other_contact.first_name)

    @less_console_noise_decorator
    def test_edit_other_contact_creates_new(self):
        """When you:
            1. edit an existing contact which IS joined to another model,
            2. then submit,
        the domain request is linked to a new contact, and the new contact is updated."""

        # Populate the database with a domain request that
        # has 1 "other contact" assigned to it, the other contact is also
        # the senior official initially
        # We'll do it from scratch
        so, _ = Contact.objects.get_or_create(
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
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )
        domain_request.other_contacts.add(so)

        # other_contact_pk is the initial pk of the other contact. set it before update
        # to be able to verify after update that the so contact is still in place
        # and not updated, and that the new contact has a new id
        other_contact_pk = so.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(
            reverse("domain-request:other_contacts", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy")

        # update the first name of the contact
        other_contacts_form["other_contacts-0-first_name"] = "Testy2"

        # Submit the updated form
        other_contacts_form.submit()

        domain_request.refresh_from_db()

        # assert that other contact info is updated, and that a new Contact
        # is created for the other contact
        other_contact = domain_request.other_contacts.all()[0]
        self.assertNotEquals(other_contact_pk, other_contact.id)
        self.assertEquals("Testy2", other_contact.first_name)
        # assert that the senior official is not updated
        senior_official = domain_request.senior_official
        self.assertEquals("Testy", senior_official.first_name)

    @less_console_noise_decorator
    def test_edit_senior_official_in_place(self):
        """When you:
            1. edit a senior official which is not joined to another model,
            2. then submit,
        the domain request is linked to the existing so, and the so updated."""

        # Populate the database with a domain request that
        # has a senior_official (so)
        # We'll do it from scratch
        so, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )

        # so_pk is the initial pk of the Senior Official. set it before update
        # to be able to verify after update that the same Contact object is in place
        so_pk = so.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        so_page = self.app.get(
            reverse("domain-request:senior_official", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        so_form = so_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(so_form["senior_official-first_name"].value, "Testy")

        # update the first name of the contact
        so_form["senior_official-first_name"] = "Testy2"

        # Submit the updated form
        so_form.submit()

        domain_request.refresh_from_db()

        # assert SO is updated "in place"
        updated_so = domain_request.senior_official
        self.assertEquals(so_pk, updated_so.id)
        self.assertEquals("Testy2", updated_so.first_name)

    @less_console_noise_decorator
    def test_edit_senior_official_creates_new(self):
        """When you:
            1. edit an existing senior official which IS joined to another model,
            2. then submit,
        the domain request is linked to a new Contact, and the new Contact is updated."""

        # Populate the database with a domain request that
        # has senior official assigned to it, the senior offical is also
        # an other contact initially
        # We'll do it from scratch
        so, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requester=self.user,
            status="started",
        )
        domain_request.other_contacts.add(so)

        # so_pk is the initial pk of the senior official. set it before update
        # to be able to verify after update that the other contact is still in place
        # and not updated, and that the new so has a new id
        so_pk = so.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        so_page = self.app.get(
            reverse("domain-request:senior_official", kwargs={"domain_request_pk": domain_request.pk})
        )
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        so_form = so_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(so_form["senior_official-first_name"].value, "Testy")

        # update the first name of the contact
        so_form["senior_official-first_name"] = "Testy2"

        # Submit the updated form
        so_form.submit()

        domain_request.refresh_from_db()

        # assert that the other contact is not updated
        other_contacts = domain_request.other_contacts.all()
        other_contact = other_contacts[0]
        self.assertEquals(so_pk, other_contact.id)
        self.assertEquals("Testy", other_contact.first_name)
        # assert that the senior official is updated
        senior_official = domain_request.senior_official
        self.assertEquals("Testy2", senior_official.first_name)

    @less_console_noise_decorator
    def test_edit_requester_in_place(self):
        """When you:
            1. edit a your user profile information,
            2. then submit,
        the domain request also updates its requester data to reflect user profile changes."""

        # Populate the database with a domain request
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            requester=self.user,
            status="started",
        )

        requester_pk = self.user.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        profile_page = self.app.get("/user-profile")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        profile_form = profile_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(profile_form["first_name"].value, self.user.first_name)

        # update the first name of the contact
        profile_form["first_name"] = "Testy2"

        # Submit the updated form
        profile_form.submit()

        domain_request.refresh_from_db()

        updated_requester = domain_request.requester
        self.assertEquals(requester_pk, updated_requester.id)
        self.assertEquals("Testy2", updated_requester.first_name)

    @less_console_noise_decorator
    def test_domain_request_about_your_organiztion_interstate(self):
        """Special districts have to answer an additional question."""
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = DomainRequest.OrganizationChoices.INTERSTATE
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.ABOUT_YOUR_ORGANIZATION])

    @less_console_noise_decorator
    def test_domain_request_tribal_government(self):
        """Tribal organizations have to answer an additional question."""
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = DomainRequest.OrganizationChoices.TRIBAL
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # the tribal government page comes immediately afterwards
        self.assertIn("/tribal_government", type_result.headers["Location"])
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        tribal_government_page = type_result.follow()

        # and the step is on the sidebar list.
        self.assertContains(tribal_government_page, self.TITLES[Step.TRIBAL_GOVERNMENT])

    @less_console_noise_decorator
    def test_domain_request_so_dynamic_text(self):
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = "federal"

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
        org_contact_form["organization_contact-federal_agency"] = self.federal_agency.id
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        # ---- SO CONTACT PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_page = org_contact_result.follow()
        self.assertContains(so_page, "Executive branch federal agencies")

        # Go back to organization type page and change type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = so_page.click(str(self.TITLES["generic_org_type"]), index=0)
        type_form = type_page.forms[0]  # IMPORTANT re-acquire a fresh form (new hidden version token)
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_form["generic_org_type-generic_org_type"] = "city"
        type_result = type_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()

        # Navigate to the org page as that is the step right before senior_official
        org_page = election_page.click(str(self.TITLES["organization_contact"]), index=0)
        org_contact_form = org_page.forms[0]
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        # Navigate back to the so page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_page = org_contact_result.follow()
        self.assertContains(so_page, "Domain requests from cities")

    @less_console_noise_decorator
    def test_domain_request_dotgov_domain_dynamic_text(self):
        intro_page = self.app.get(reverse("domain-request:start"))
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
        type_form["generic_org_type-generic_org_type"] = "federal"

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
        org_contact_form["organization_contact-federal_agency"] = self.federal_agency.id
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        # ---- SO CONTACT PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_page = org_contact_result.follow()

        # ---- senior OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_page = org_contact_result.follow()
        so_form = so_page.forms[0]
        so_form["senior_official-first_name"] = "Testy ATO"
        so_form["senior_official-last_name"] = "Tester ATO"
        so_form["senior_official-title"] = "Chief Tester"
        so_form["senior_official-email"] = "testy@town.com"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        so_result = so_form.submit()

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = so_result.follow()
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
        type_page = dotgov_page.click(str(self.TITLES["generic_org_type"]), index=0)
        type_form = type_page.forms[0]  # IMPORTANT re-acquire a fresh form (new hidden version token)
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_form["generic_org_type-generic_org_type"] = "city"
        type_result = type_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_websites = election_page.click(str(self.TITLES["current_sites"]), index=0)
        current_sites_form = current_websites.forms[0]
        current_sites_form["current_sites-0-website"] = "www.city.com"
        current_sites_result = current_sites_form.submit().follow()

        # Go back to dotgov domain page to test the dynamic text changed
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = current_sites_result.click(str(self.TITLES["dotgov_domain"]), index=0)
        self.assertContains(dotgov_page, "CityofEudoraKS.gov")
        self.assertNotContains(dotgov_page, "medicare.gov")

    # @less_console_noise_decorator
    def test_domain_request_FEB_questions(self):
        """
        Test that for a member of a federal executive branch portfolio with org feature on, the dotgov domain page
        contains additional questions for OMB.
        """
        agency, _ = FederalAgency.objects.get_or_create(
            agency="US Treasury Dept",
            federal_type=BranchChoices.EXECUTIVE,
        )

        portfolio, _ = Portfolio.objects.get_or_create(
            requester=self.user,
            organization_name="Test Portfolio",
            organization_type=Portfolio.OrganizationChoices.FEDERAL,
            federal_agency=agency,
        )

        portfolio_perm, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        intro_page = self.app.get(reverse("domain-request:start"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[1] if len(intro_page.forms) > 1 else intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        portfolio_requesting_entity = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- REQUESTING ENTITY PAGE  ----
        try:
            requesting_entity_form = portfolio_requesting_entity.forms[0]
            _ = requesting_entity_form["portfolio_requesting_entity-requesting_entity_is_suborganization"]
        except (KeyError, IndexError):
            requesting_entity_form = portfolio_requesting_entity.forms[1]

        requesting_entity_form["portfolio_requesting_entity-requesting_entity_is_suborganization"] = False

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requesting_entity_result = requesting_entity_form.submit()

        # ---- DOTGOV DOMAIN PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = requesting_entity_result.follow()

        # separate out these tests for readability
        self.feb_dotgov_domain_tests(dotgov_page)

        domain_form = form_with_field(dotgov_page, "dotgov_domain-requested_domain")
        domain = "test.gov"
        domain_form["dotgov_domain-requested_domain"] = domain
        domain_form["dotgov_domain-feb_naming_requirements"] = "False"
        domain_form["dotgov_domain-feb_naming_requirements_details"] = "Because this is a test"
        with patch(
            "registrar.forms.domain_request_wizard.DotGovDomainForm.clean_requested_domain", return_value=domain
        ):  # noqa
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            domain_result = domain_form.submit()

        # ---- PURPOSE PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_page = domain_result.follow()

        self.feb_purpose_page_tests(purpose_page)

        purpose_form = form_with_field(purpose_page, "purpose-feb_purpose_choice")
        purpose_form["purpose-feb_purpose_choice"] = "redirect"
        purpose_form["purpose-purpose"] = "testPurpose123"
        purpose_form["purpose-has_timeframe"] = "True"
        purpose_form["purpose-time_frame_details"] = "1/2/2025 - 1/2/2026"
        purpose_form["purpose-is_interagency_initiative"] = "True"
        purpose_form["purpose-interagency_initiative_details"] = "FakeInteragencyInitiative"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_result = purpose_form.submit()

        # ---- ADDITIONAL DETAILS PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        additional_details_page = purpose_result.follow()
        self.feb_additional_details_page_tests(additional_details_page)

        additional_details_form = form_with_field(additional_details_page, "portfolio_additional_details-anything_else")
        additional_details_form["portfolio_additional_details-has_anything_else_text"] = "True"
        additional_details_form["portfolio_additional_details-anything_else"] = "test"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        additional_details_result = additional_details_form.submit()

        # ---- REQUIREMENTS PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_page = additional_details_result.follow()
        self.feb_requirements_page_tests(requirements_page)

        requirements_form = form_with_field(requirements_page, "requirements-is_policy_acknowledged")
        requirements_form["requirements-is_policy_acknowledged"] = "True"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_result = requirements_form.submit()

        # ---- REVIEW PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        review_page = requirements_result.follow()
        self.feb_review_page_tests(review_page)

    def feb_purpose_page_tests(self, purpose_page):
        # Check for the 21st Century IDEA Act links
        self.assertContains(purpose_page, "https://digital.gov/resources/delivering-digital-first-public-experience/")
        self.assertContains(
            purpose_page,
            "https://whitehouse.gov/wp-content/uploads/2023/09/M-23-22-Delivering-a-Digital-First-Public-Experience.pdf",  # noqa
        )

        self.assertContains(purpose_page, "What is the purpose of your requested domain?")

        # Make sure the purpose selector form is present
        self.assertContains(purpose_page, "feb_purpose_choice")

        # Make sure the purpose details form is present
        self.assertContains(purpose_page, "purpose-details")

        # Make sure the timeframe yes/no form is present
        self.assertContains(purpose_page, "purpose-has_timeframe")

        # Make sure the timeframe details form is present
        self.assertContains(purpose_page, "purpose-time_frame_details")

        # Make sure the interagency initiative yes/no form is present
        self.assertContains(purpose_page, "purpose-is_interagency_initiative")

        # Make sure the interagency initiative details form is present
        self.assertContains(purpose_page, "purpose-interagency_initiative_details")

    def feb_dotgov_domain_tests(self, dotgov_page):
        # Make sure the dynamic example content doesn't show
        self.assertNotContains(dotgov_page, "medicare.gov")

        # Make sure the link at the top directs to OPM FEB guidance
        self.assertContains(dotgov_page, "https://get.gov/domains/executive-branch-guidance/")

        # Check for header of first FEB form
        self.assertContains(dotgov_page, "Does this submission meet each domain naming requirement?")

        # Check for label of second FEB form
        self.assertContains(dotgov_page, "Provide details")

        # Check that the yes/no form was included
        self.assertContains(dotgov_page, "feb_naming_requirements")

        # Check that the details form was included
        self.assertContains(dotgov_page, "feb_naming_requirements_details")

    def feb_additional_details_page_tests(self, additional_details_page):

        # Make sure the additional details form is present
        self.assertContains(additional_details_page, "additional_details-has_anything_else_text")
        self.assertContains(additional_details_page, "additional_details-anything_else")

    def feb_requirements_page_tests(self, requirements_page):

        # Check for the policy acknowledgement form
        self.assertContains(requirements_page, "is_policy_acknowledged")
        self.assertContains(
            requirements_page,
            "I read and agree to the requirements for operating a .gov domain.",
        )

    def feb_review_page_tests(self, review_page):
        # Meets naming requirements
        self.assertContains(review_page, "Meets naming requirements")
        self.assertContains(review_page, "No")
        self.assertContains(review_page, "Because this is a test")
        # Purpose
        self.assertContains(review_page, "Purpose")
        self.assertContains(review_page, "Used as a redirect for an existing or new website")
        self.assertContains(review_page, "testPurpose123")
        # Target time frame
        self.assertContains(review_page, "Target time frame")
        self.assertContains(review_page, "1/2/2025 - 1/2/2026")
        # Interagency initiative
        self.assertContains(review_page, "Interagency initiative")
        self.assertContains(review_page, "FakeInteragencyInitiative")

    @less_console_noise_decorator
    def test_domain_request_formsets(self):
        """Users are able to add more than one of some fields."""
        DomainRequest.objects.all().delete()

        # Create a new domain request
        intro_page = self.app.get(reverse("domain-request:start"))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_form.submit()

        all_domain_requests = DomainRequest.objects.all()
        self.assertEqual(all_domain_requests.count(), 1)

        new_domain_request_id = all_domain_requests.first().id

        # Skip to the current sites page
        current_sites_page = self.app.get(
            reverse("domain-request:current_sites", kwargs={"domain_request_pk": new_domain_request_id})
        )
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

        all_domain_requests = DomainRequest.objects.all()
        self.assertEqual(all_domain_requests.count(), 1, msg="Expected one domain request but got multiple")
        # and it is correctly referenced in the ManyToOne relationship
        domain_request = all_domain_requests.first()  # there's only one
        self.assertEqual(
            domain_request.current_websites.filter(website="https://example.com").count(),
            1,
        )

    @skip("WIP")
    def test_domain_request_edit_restore(self):
        """
        Test that a previously saved domain request is available at the /edit endpoint.
        """
        so, _ = Contact.objects.get_or_create(
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
        domain_request, _ = DomainRequest.objects.get_or_create(
            generic_org_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            senior_official=so,
            requested_domain=domain,
            requester=self.user,
        )
        domain_request.other_contacts.add(other)
        domain_request.current_websites.add(current)
        domain_request.alternative_domains.add(alt)

        # prime the form by visiting /edit
        url = reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk})
        response = self.client.get(url)

        # TODO: this is a sketch of each page in the wizard which needs to be tested
        # Django does not have tools sufficient for real end to end integration testing
        # (for example, USWDS moves radio buttons off screen and replaces them with
        # CSS styled "fakes" -- Django cannot determine if those are visually correct)
        # -- the best that can/should be done here is to ensure the correct values
        # are being passed to the templating engine

        url = reverse("domain-request:generic_org_type")
        response = self.client.get(url, follow=True)
        self.assertContains(response, "<input>")
        # choices = response.context['wizard']['form']['generic_org_type'].subwidgets
        # radio = [ x for x in choices if x.data["value"] == "federal" ][0]
        # checked = radio.data["selected"]
        # self.assertTrue(checked)

        # url = reverse("domain-request:organization_federal")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:organization_contact")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:senior_official")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:current_sites")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:dotgov_domain")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:purpose")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:your_contact")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:other_contacts")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:other_contacts")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:security_email")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:anything_else")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("domain-request:requirements")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

    @less_console_noise_decorator
    def test_long_org_name_in_domain_request(self):
        """
        Make sure the long name is displaying in the domain request form,
        org step
        """
        intro_page = self.app.get(reverse("domain-request:start"))
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

    @less_console_noise_decorator
    def test_submit_modal_no_domain_text_fallback(self):
        """When user clicks on submit your domain request and the requested domain
        is null (possible through url direct access to the review page), present
        fallback copy in the modal's header.

        NOTE: This may be a moot point if we implement a more solid pattern in the
        future, like not a submit action at all on the review page."""

        review_page = self.app.get(reverse("domain-request:review", kwargs={"domain_request_pk": 0}))
        self.assertContains(review_page, "toggle-submit-domain-request")
        self.assertContains(review_page, "Your request form is incomplete")

    def test_portfolio_user_missing_edit_permissions(self):
        """Tests that a portfolio user without edit request permissions cannot edit or add new requests"""
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Test Portfolio")
        portfolio_perm, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        )
        # This user should be forbidden from creating new domain requests
        intro_page = self.app.get(reverse("domain-request:start"), expect_errors=True)
        self.assertEqual(intro_page.status_code, 403)

        # This user should also be forbidden from editing existing ones
        domain_request = completed_domain_request(user=self.user)
        edit_page = self.app.get(
            reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}), expect_errors=True
        )
        self.assertEqual(edit_page.status_code, 403)

        # Cleanup
        portfolio_perm.delete()
        portfolio.delete()

    def test_portfolio_user_with_edit_permissions(self):
        """Tests that a portfolio user with edit request permissions can edit and add new requests"""
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Test Portfolio")
        portfolio_perm, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[UserPortfolioPermissionChoices.EDIT_REQUESTS],
        )

        # This user should be allowed to create new domain requests
        intro_page = self.app.get(reverse("domain-request:start"))
        self.assertEqual(intro_page.status_code, 200)

        # This user should also be allowed to edit existing ones
        domain_request = completed_domain_request(user=self.user, portfolio=portfolio)
        edit_page = self.app.get(
            reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk})
        ).follow()
        self.assertEqual(edit_page.status_code, 200)

    def test_non_requester_access(self):
        """Tests that a user cannot edit a domain request they didn't create"""
        p = "password"
        other_user = User.objects.create_user(username="other_user", password=p)
        domain_request = completed_domain_request(user=other_user)

        edit_page = self.app.get(
            reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk}), expect_errors=True
        )
        self.assertEqual(edit_page.status_code, 403)

    def test_requester_access(self):
        """Tests that a user can edit a domain request they created"""
        domain_request = completed_domain_request(user=self.user)

        edit_page = self.app.get(
            reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.pk})
        ).follow()
        self.assertEqual(edit_page.status_code, 200)


class DomainRequestTestDifferentStatuses(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()

    @less_console_noise_decorator
    def test_domain_request_status(self):
        """Checking domain request status page"""
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.user)
        domain_request.save()

        detail_page = self.app.get(f"/domain-request/{domain_request.id}")
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Status:")

    @less_console_noise_decorator
    def test_domain_request_status_with_ineligible_user(self):
        """Checking domain request status page whith a blocked user.
        The user should still have access to view."""
        self.user.status = "ineligible"
        self.user.save()

        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.user)
        domain_request.save()

        detail_page = self.app.get(f"/domain-request/{domain_request.id}")
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Status:")

    @less_console_noise_decorator
    def test_domain_request_withdraw(self):
        """Checking domain request status page"""
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.user)
        domain_request.save()

        detail_page = self.app.get(f"/domain-request/{domain_request.id}")
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
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
        response = self.client.get("/get-domain-requests-json/")
        self.assertContains(response, "Withdrawn")

    @less_console_noise_decorator
    def test_domain_request_withdraw_portfolio_redirects_correctly(self):
        """Tests that the withdraw button on portfolio redirects to the portfolio domain requests page"""
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Test Portfolio")
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[UserPortfolioPermissionChoices.EDIT_REQUESTS],
        )
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.user, portfolio=portfolio
        )
        domain_request.save()

        detail_page = self.app.get(f"/domain-request/{domain_request.id}")
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Status:")
        # click the "Withdraw request" button
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                withdraw_page = detail_page.click("Withdraw request")
                self.assertContains(withdraw_page, "Withdraw request for")
                home_page = withdraw_page.click("Withdraw request")

        # Assert that it redirects to the portfolio requests page and the status has been updated to withdrawn
        self.assertEqual(home_page.status_code, 302)
        self.assertEqual(home_page.location, reverse("domain-requests"))

        response = self.client.get("/get-domain-requests-json/")
        self.assertContains(response, "Withdrawn")

    @less_console_noise_decorator
    def test_domain_request_withdraw_no_permissions(self):
        """Can't withdraw domain requests as a restricted user."""
        self.user.status = User.RESTRICTED
        self.user.save()
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.user)
        domain_request.save()

        detail_page = self.client.get(f"/domain-request/{domain_request.id}")
        self.assertEqual(detail_page.status_code, 403)
        # Restricted user trying to withdraw results in 403 error
        with less_console_noise():
            for url_name in [
                "domain-request-withdraw-confirmation",
                "domain-request-withdrawn",
            ]:
                with self.subTest(url_name=url_name):
                    page = self.client.get(reverse(url_name, kwargs={"domain_request_pk": domain_request.pk}))
                    self.assertEqual(page.status_code, 403)

    @less_console_noise_decorator
    def test_domain_request_status_no_permissions(self):
        """Can't access domain requests without being the requester."""
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.user)
        other_user = User()
        other_user.save()
        domain_request.requester = other_user
        domain_request.save()

        # PermissionDeniedErrors make lots of noise in test output
        with less_console_noise():
            for url_name in [
                "domain-request-status",
                "domain-request-withdraw-confirmation",
                "domain-request-withdrawn",
            ]:
                with self.subTest(url_name=url_name):
                    page = self.client.get(reverse(url_name, kwargs={"domain_request_pk": domain_request.pk}))
                    self.assertEqual(page.status_code, 403)

    @less_console_noise_decorator
    def test_approved_domain_request_not_in_active_requests(self):
        """An approved domain request is not shown in the Active
        Requests table on home.html."""
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED, user=self.user)
        domain_request.save()

        home_page = self.app.get("/")
        # This works in our test environment because creating
        # an approved domain request here does not generate a
        # domain object, so we do not expect to see 'city.gov'
        # in either the Domains or Requests tables.
        self.assertNotContains(home_page, "city.gov")


class TestDomainRequestWizard(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.wizard = DomainRequestWizard()
        # Mock the request object, its user, and session attributes appropriately
        self.wizard.request = Mock(user=self.user, session={})

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()

    @less_console_noise_decorator
    def test_breadcrumb_navigation(self):
        """
        Tests the breadcrumb navigation behavior in domain request wizard.
        Ensures that:
        - Breadcrumb shows correct text based on portfolio flag
        - Links point to correct destinations
        - Back button appears on appropriate steps
        - Back button is not present on first step
        """
        # Create initial domain request
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            user=self.user,
        )

        # Test without portfolio flag
        start_page = self.app.get(f"/domain-request/{domain_request.id}/edit/").follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Check initial breadcrumb state.
        # Ensure that the request name is shown if it exists, otherwise just show new domain request.
        self.assertContains(start_page, '<ol class="usa-breadcrumb__list">')
        self.assertContains(start_page, "city.gov")
        self.assertContains(start_page, 'href="/"')
        self.assertContains(start_page, "Home")
        self.assertNotContains(start_page, "Previous step")

        # Move to next step
        form = start_page.forms[0]
        next_page = form.submit().follow()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the back button appears
        self.assertContains(next_page, "Back")

        portfolio = Portfolio.objects.create(
            requester=self.user,
            organization_name="test portfolio",
        )
        permission = UserPortfolioPermission.objects.create(
            user=self.user,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[UserPortfolioPermissionChoices.EDIT_REQUESTS],
        )
        domain_request.portfolio = portfolio
        domain_request.save()
        domain_request.refresh_from_db()

        # Check portfolio-specific breadcrumb
        portfolio_page = self.app.get(f"/domain-request/{domain_request.id}/edit/").follow()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        self.assertContains(portfolio_page, "Domain requests")
        domain_request.portfolio = None
        domain_request.save()
        # Clean up portfolio
        permission.delete()
        portfolio.delete()

        # Clean up
        domain_request.delete()

    @less_console_noise_decorator
    def test_unlocked_steps_empty_domain_request(self):
        """Test when all fields in the domain request are empty."""
        unlocked_steps = self.wizard.db_check_for_unlocking_steps()
        expected_dict = []
        self.assertEqual(unlocked_steps, expected_dict)

    @less_console_noise_decorator
    def test_unlocked_steps_full_domain_request(self):
        """Test when all fields in the domain request are filled."""

        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.STARTED, user=self.user)
        domain_request.anything_else = False
        domain_request.has_anything_else_text = False
        domain_request.save()

        response = self.app.get(f"/domain-request/{domain_request.id}/edit/")
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Check if the response is a redirect
        if response.status_code == 302:
            # Follow the redirect manually
            try:
                detail_page = response.follow()

                self.wizard.get_context_data()
            except Exception as err:
                # Handle any potential errors while following the redirect
                self.fail(f"Error following the redirect {err}")

            # Now 'detail_page' contains the response after following the redirect
            self.assertEqual(detail_page.status_code, 200)

            # 10 unlocked steps, one active step, the review step will have link_usa but not check_circle
            self.assertContains(detail_page, "#check_circle", count=9)
            # Type of organization
            self.assertContains(detail_page, "usa-current", count=2)
            self.assertContains(detail_page, "link_usa-checked", count=10)

        else:
            self.fail(f"Expected a redirect, but got a different response: {response}")

    @less_console_noise_decorator
    def test_unlocked_steps_partial_domain_request(self):
        """Test when some fields in the domain request are filled."""

        # Create the site and contacts to delete (orphaned)
        contact = Contact.objects.create(
            first_name="Henry", last_name="Mcfakerson", title="test", email="moar@igorville.gov", phone="1234567890"
        )
        # Create two non-orphaned contacts
        contact_2 = Contact.objects.create(
            first_name="Saturn", last_name="Mars", title="test", email="moar@igorville.gov", phone="1234567890"
        )

        # Attach a user object to a contact (should not be deleted)
        contact_user, _ = Contact.objects.get_or_create(
            first_name="Hank", last_name="McFakey", title="test", email="moar@igorville.gov", phone="1234567890"
        )

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            requester=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            senior_official=contact,
        )
        domain_request.other_contacts.set([contact_2])

        response = self.app.get(f"/domain-request/{domain_request.id}/edit/")
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Check if the response is a redirect
        if response.status_code == 302:
            # Follow the redirect manually
            try:
                detail_page = response.follow()

                self.wizard.get_context_data()
            except Exception as err:
                # Handle any potential errors while following the redirect
                self.fail(f"Error following the redirect {err}")

            # Now 'detail_page' contains the response after following the redirect
            self.assertEqual(detail_page.status_code, 200)

            # 5 unlocked steps (so, domain, other contacts, and current sites
            # which unlocks if domain exists), one active step, the review step is locked
            self.assertContains(detail_page, "#check_circle", count=4)
            # Type of organization
            self.assertContains(detail_page, "usa-current", count=2)
            self.assertContains(detail_page, "link_usa-checked", count=4)

        else:
            self.fail(f"Expected a redirect, but got a different response: {response}")

    @less_console_noise_decorator
    def test_wizard_steps_portfolio(self):
        """
        Tests the behavior of the domain request wizard for portfolios.
        Ensures that:
        - The user can access the organization page.
        - The expected number of steps are locked/unlocked (implicit test for expected steps).
        - The user lands on the "Requesting entity" page
        - The user does not see the Domain and Domain requests buttons
        """

        federal_agency = FederalAgency.objects.get(agency="Non-Federal Agency")
        # Add a portfolio
        portfolio = Portfolio.objects.create(
            requester=self.user,
            organization_name="test portfolio",
            federal_agency=federal_agency,
        )

        user_portfolio_permission = UserPortfolioPermission.objects.create(
            user=self.user,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
            ],
        )

        # This should unlock 4 steps by default.
        # Purpose, .gov domain, current websites, and requirements for operating
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED, user=self.user, portfolio=portfolio
        )
        domain_request.anything_else = None
        domain_request.save()

        response = self.app.get(f"/domain-request/{domain_request.id}/edit/")
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Check if the response is a redirect
        if response.status_code == 302:
            # Follow the redirect manually
            try:
                detail_page = response.follow()
                self.wizard.get_context_data()
            except Exception as err:
                # Handle any potential errors while following the redirect
                self.fail(f"Error following the redirect {err}")

            # Now 'detail_page' contains the response after following the redirect
            self.assertEqual(detail_page.status_code, 200)

            # Assert that we're on the organization page
            self.assertContains(detail_page, portfolio.organization_name)

            # We should only see one unlocked step
            self.assertContains(detail_page, "#check_circle", count=3)

            # One pages should still be locked (additional details)
            self.assertContains(detail_page, "#lock", 1)

            # The current option should be selected
            self.assertContains(detail_page, "usa-current", count=3)

            # We default to the requesting entity page
            expected_url = reverse(
                "domain-request:portfolio_requesting_entity", kwargs={"domain_request_pk": domain_request.id}
            )
            # This returns the entire url, thus "in"
            self.assertIn(expected_url, detail_page.request.url)
        else:
            self.fail(f"Expected a redirect, but got a different response: {response}")

        # Data cleanup
        domain_request.portfolio = None
        domain_request.save()
        user_portfolio_permission.delete()
        portfolio.delete()
        federal_agency.delete()
        domain_request.delete()

    @less_console_noise_decorator
    def test_unlock_organization_contact_flags_enabled(self):
        """Tests unlock_organization_contact when agency exists in a portfolio"""
        # Create a federal agency
        federal_agency = FederalAgency.objects.create(agency="Portfolio Agency")

        # Create a portfolio with matching organization name
        Portfolio.objects.create(
            requester=self.user, organization_name=federal_agency.agency, federal_agency=federal_agency
        )

        # Create domain request with the portfolio agency
        domain_request = completed_domain_request(federal_agency=federal_agency, user=self.user)
        self.assertFalse(domain_request.unlock_organization_contact())

    @less_console_noise_decorator
    def test_unlock_organization_contact_flags_disabled(self):
        """Tests unlock_organization_contact when organization flags are disabled"""
        # Create a federal agency
        federal_agency = FederalAgency.objects.create(agency="Portfolio Agency")

        # Create a portfolio with matching organization name
        Portfolio.objects.create(requester=self.user, organization_name=federal_agency.agency)

        domain_request = completed_domain_request(federal_agency=federal_agency, user=self.user)
        self.assertTrue(domain_request.unlock_organization_contact())


class TestPortfolioDomainRequestViewonly(TestWithUser, WebTest):

    # Doesn't work with CSRF checking
    # hypothesis is that CSRF_USE_SESSIONS is incompatible with WebTest
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.federal_agency, _ = FederalAgency.objects.get_or_create(agency="General Services Administration")
        self.app.set_user(self.user.username)
        self.TITLES = DomainRequestWizard.REGULAR_TITLES

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        self.federal_agency.delete()

    @less_console_noise_decorator
    def test_domain_request_viewonly_displays_correct_fields(self):
        """Tests that the viewonly page displays different fields"""
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Test Portfolio")
        UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        dummy_user, _ = User.objects.get_or_create(username="testusername123456")
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.SUBMITTED, user=dummy_user, portfolio=portfolio
        )
        domain_request.save()

        detail_page = self.app.get(f"/domain-request/viewonly/{domain_request.id}")
        self.assertContains(detail_page, "Requesting entity")
        self.assertNotContains(detail_page, "Type of organization")
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "Status:")
