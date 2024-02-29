from datetime import date
from django.test import TestCase, RequestFactory, Client, override_settings
from django.contrib.admin.sites import AdminSite
from contextlib import ExitStack
from django_webtest import WebTest  # type: ignore
from django.contrib import messages
from django.urls import reverse
from registrar.admin import (
    DomainAdmin,
    DomainRequestAdmin,
    DomainRequestAdminForm,
    DomainInvitationAdmin,
    ListHeaderAdmin,
    MyUserAdmin,
    AuditedAdmin,
    ContactAdmin,
    DomainInformationAdmin,
    UserDomainRoleAdmin,
    VerifiedByStaffAdmin,
)
from registrar.models import Domain, DomainRequest, DomainInformation, User, DomainInvitation, Contact, Website
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.verified_by_staff import VerifiedByStaff
from .common import (
    MockSESClient,
    AuditedAdminMockData,
    completed_domain_request,
    generic_domain_object,
    less_console_noise,
    mock_user,
    create_superuser,
    create_user,
    create_ready_domain,
    multiple_unalphabetical_domain_objects,
    MockEppLib,
    GenericTestHelper,
)
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user_model
from unittest.mock import ANY, call, patch
from unittest import skip

from django.conf import settings
import boto3_mocking  # type: ignore
import logging

logger = logging.getLogger(__name__)


class TestDomainAdmin(MockEppLib, WebTest):
    # csrf checks do not work with WebTest.
    # We disable them here. TODO for another ticket.
    csrf_checks = False

    def setUp(self):
        self.site = AdminSite()
        self.admin = DomainAdmin(model=Domain, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.factory = RequestFactory()
        self.app.set_user(self.superuser.username)
        self.client.force_login(self.superuser)
        super().setUp()

    @skip("TODO for another ticket. This test case is grabbing old db data.")
    @patch("registrar.admin.DomainAdmin._get_current_date", return_value=date(2024, 1, 1))
    def test_extend_expiration_date_button(self, mock_date_today):
        """
        Tests if extend_expiration_date button extends correctly
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        # Make sure the ex date is what we expect it to be
        domain_ex_date = Domain.objects.get(id=domain.id).expiration_date
        self.assertEqual(domain_ex_date, date(2023, 5, 25))

        # Make sure that the page is loading as expected
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Grab the form to submit
        form = response.forms["domain_form"]

        with patch("django.contrib.messages.add_message") as mock_add_message:
            # Submit the form
            response = form.submit("_extend_expiration_date")

            # Follow the response
            response = response.follow()

        # refresh_from_db() does not work for objects with protected=True.
        # https://github.com/viewflow/django-fsm/issues/89
        new_domain = Domain.objects.get(id=domain.id)

        # Check that the current expiration date is what we expect
        self.assertEqual(new_domain.expiration_date, date(2025, 5, 25))

        # Assert that everything on the page looks correct
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Ensure the message we recieve is in line with what we expect
        expected_message = "Successfully extended the expiration date."
        expected_call = call(
            # The WGSI request doesn't need to be tested
            ANY,
            messages.INFO,
            expected_message,
            extra_tags="",
            fail_silently=False,
        )
        mock_add_message.assert_has_calls([expected_call], 1)

    @patch("registrar.admin.DomainAdmin._get_current_date", return_value=date(2024, 1, 1))
    def test_extend_expiration_date_button_epp(self, mock_date_today):
        """
        Tests if extend_expiration_date button sends the right epp command
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        # Make sure that the page is loading as expected
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Grab the form to submit
        form = response.forms["domain_form"]

        with patch("django.contrib.messages.add_message") as mock_add_message:
            with patch("registrar.models.Domain.renew_domain") as renew_mock:
                # Submit the form
                response = form.submit("_extend_expiration_date")

                # Follow the response
                response = response.follow()

        # This value is based off of the current year - the expiration date.
        # We "freeze" time to 2024, so 2024 - 2023 will always result in an
        # "extension" of 2, as that will be one year of extension from that date.
        extension_length = 2

        # Assert that it is calling the function with the right extension length.
        # We only need to test the value that EPP sends, as we can assume the other
        # test cases cover the "renew" function.
        renew_mock.assert_has_calls([call(length=extension_length)], any_order=False)

        # We should not make duplicate calls
        self.assertEqual(renew_mock.call_count, 1)

        # Assert that everything on the page looks correct
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Ensure the message we recieve is in line with what we expect
        expected_message = "Successfully extended the expiration date."
        expected_call = call(
            # The WGSI request doesn't need to be tested
            ANY,
            messages.INFO,
            expected_message,
            extra_tags="",
            fail_silently=False,
        )
        mock_add_message.assert_has_calls([expected_call], 1)

    @patch("registrar.admin.DomainAdmin._get_current_date", return_value=date(2023, 1, 1))
    def test_extend_expiration_date_button_date_matches_epp(self, mock_date_today):
        """
        Tests if extend_expiration_date button sends the right epp command
        when the current year matches the expiration date
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        # Make sure that the page is loading as expected
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Grab the form to submit
        form = response.forms["domain_form"]

        with patch("django.contrib.messages.add_message") as mock_add_message:
            with patch("registrar.models.Domain.renew_domain") as renew_mock:
                # Submit the form
                response = form.submit("_extend_expiration_date")

                # Follow the response
                response = response.follow()

        extension_length = 1

        # Assert that it is calling the function with the right extension length.
        # We only need to test the value that EPP sends, as we can assume the other
        # test cases cover the "renew" function.
        renew_mock.assert_has_calls([call(length=extension_length)], any_order=False)

        # We should not make duplicate calls
        self.assertEqual(renew_mock.call_count, 1)

        # Assert that everything on the page looks correct
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Ensure the message we recieve is in line with what we expect
        expected_message = "Successfully extended the expiration date."
        expected_call = call(
            # The WGSI request doesn't need to be tested
            ANY,
            messages.INFO,
            expected_message,
            extra_tags="",
            fail_silently=False,
        )
        mock_add_message.assert_has_calls([expected_call], 1)

    def test_short_org_name_in_domains_list(self):
        """
        Make sure the short name is displaying in admin on the list page
        """
        with less_console_noise():
            self.client.force_login(self.superuser)
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            mock_client = MockSESClient()
            with boto3_mocking.clients.handler_for("sesv2", mock_client):
                domain_request.approve()

            response = self.client.get("/admin/registrar/domain/")

            # There are 4 template references to Federal (4) plus four references in the table
            # for our actual application
            self.assertContains(response, "Federal", count=8)
            # This may be a bit more robust
            self.assertContains(response, '<td class="field-organization_type">Federal</td>', count=1)
            # Now let's make sure the long description does not exist
            self.assertNotContains(response, "Federal: an agency of the U.S. government")

    @skip("Why did this test stop working, and is is a good test")
    def test_place_and_remove_hold(self):
        domain = create_ready_domain()
        # get admin page and assert Place Hold button
        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Place hold")
        self.assertNotContains(response, "Remove hold")

        # submit place_client_hold and assert Remove Hold button
        response = self.client.post(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            {"_place_client_hold": "Place hold", "name": domain.name},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Remove hold")
        self.assertNotContains(response, "Place hold")

        # submit remove client hold and assert Place hold button
        response = self.client.post(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            {"_remove_client_hold": "Remove hold", "name": domain.name},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Place hold")
        self.assertNotContains(response, "Remove hold")

    def test_deletion_is_successful(self):
        """
        Scenario: Domain deletion is unsuccessful
            When the domain is deleted
            Then a user-friendly success message is returned for displaying on the web
            And `state` is et to `DELETED`
        """
        with less_console_noise():
            domain = create_ready_domain()
            # Put in client hold
            domain.place_client_hold()
            p = "userpass"
            self.client.login(username="staffuser", password=p)
            # Ensure everything is displaying correctly
            response = self.client.get(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain.name)
            self.assertContains(response, "Remove from registry")
            # Test the info dialog
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.INFO,
                    "Domain city.gov has been deleted. Thanks!",
                    extra_tags="",
                    fail_silently=False,
                )
            self.assertEqual(domain.state, Domain.State.DELETED)

    def test_deletion_ready_fsm_failure(self):
        """
        Scenario: Domain deletion is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
            And `state` is not set to `DELETED`
        """
        with less_console_noise():
            domain = create_ready_domain()
            p = "userpass"
            self.client.login(username="staffuser", password=p)
            # Ensure everything is displaying correctly
            response = self.client.get(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain.name)
            self.assertContains(response, "Remove from registry")
            # Test the error
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.ERROR,
                    "Error deleting this Domain: "
                    "Can't switch from state 'ready' to 'deleted'"
                    ", must be either 'dns_needed' or 'on_hold'",
                    extra_tags="",
                    fail_silently=False,
                )

        self.assertEqual(domain.state, Domain.State.READY)

    def test_analyst_deletes_domain_idempotent(self):
        """
        Scenario: Analyst tries to delete an already deleted domain
            Given `state` is already `DELETED`
            When `domain.deletedInEpp()` is called
            Then `commands.DeleteDomain` is sent to the registry
            And Domain returns normally without an error dialog
        """
        with less_console_noise():
            domain = create_ready_domain()
            # Put in client hold
            domain.place_client_hold()
            p = "userpass"
            self.client.login(username="staffuser", password=p)
            # Ensure everything is displaying correctly
            response = self.client.get(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain.name)
            self.assertContains(response, "Remove from registry")
            # Test the info dialog
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            # Delete it once
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.INFO,
                    "Domain city.gov has been deleted. Thanks!",
                    extra_tags="",
                    fail_silently=False,
                )

            self.assertEqual(domain.state, Domain.State.DELETED)
            # Try to delete it again
            # Test the info dialog
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.INFO,
                    "This domain is already deleted",
                    extra_tags="",
                    fail_silently=False,
                )
            self.assertEqual(domain.state, Domain.State.DELETED)

    @skip("Waiting on epp lib to implement")
    def test_place_and_remove_hold_epp(self):
        raise

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()


class TestDomainRequestAdminForm(TestCase):
    def setUp(self):
        # Create a test application with an initial state of started
        self.domain_request = completed_domain_request()

    def test_form_choices(self):
        with less_console_noise():
            # Create a form instance with the test application
            form = DomainRequestAdminForm(instance=self.domain_request)

            # Verify that the form choices match the available transitions for started
            expected_choices = [("started", "Started"), ("submitted", "Submitted")]
            self.assertEqual(form.fields["status"].widget.choices, expected_choices)

    def test_form_choices_when_no_instance(self):
        with less_console_noise():
            # Create a form instance without an instance
            form = DomainRequestAdminForm()

            # Verify that the form choices show all choices when no instance is provided;
            # this is necessary to show all choices when creating a new domain
            # application in django admin;
            # note that FSM ensures that no domain request exists with invalid status,
            # so don't need to test for invalid status
            self.assertEqual(
                form.fields["status"].widget.choices,
                DomainRequest._meta.get_field("status").choices,
            )

    def test_form_choices_when_ineligible(self):
        with less_console_noise():
            # Create a form instance with a domain request with ineligible status
            ineligible_domain_request = DomainRequest(status="ineligible")

            # Attempt to create a form with the ineligible application
            # The form should not raise an error, but choices should be the
            # full list of possible choices
            form = DomainRequestAdminForm(instance=ineligible_domain_request)

            self.assertEqual(
                form.fields["status"].widget.choices,
                DomainRequest._meta.get_field("status").choices,
            )


@boto3_mocking.patching
class TestDomainRequestAdmin(MockEppLib):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = DomainRequestAdmin(model=DomainRequest, admin_site=self.site)
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/DomainRequest/",
            model=DomainRequest,
        )
        self.mock_client = MockSESClient()

    def test_domain_sortable(self):
        """Tests if the DomainRequest sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            multiple_unalphabetical_domain_objects("domain_request")

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("1", ("requested_domain__name",))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-1", ("-requested_domain__name",))

    def test_submitter_sortable(self):
        """Tests if the DomainRequest sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            multiple_unalphabetical_domain_objects("domain_request")

            additional_domain_request = generic_domain_object("domain_request", "Xylophone")
            new_user = User.objects.filter(username=additional_domain_request.investigator.username).get()
            new_user.first_name = "Xylophonic"
            new_user.save()

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted(
                "11",
                (
                    "submitter__first_name",
                    "submitter__last_name",
                ),
            )

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted(
                "-11",
                (
                    "-submitter__first_name",
                    "-submitter__last_name",
                ),
            )

    def test_investigator_sortable(self):
        """Tests if the DomainRequest sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            multiple_unalphabetical_domain_objects("domain_request")
            additional_domain_request = generic_domain_object("domain_request", "Xylophone")
            new_user = User.objects.filter(username=additional_domain_request.investigator.username).get()
            new_user.first_name = "Xylophonic"
            new_user.save()

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted(
                "6",
                (
                    "investigator__first_name",
                    "investigator__last_name",
                ),
            )

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted(
                "-6",
                (
                    "-investigator__first_name",
                    "-investigator__last_name",
                ),
            )

    def test_short_org_name_in_domain_requests_list(self):
        """
        Make sure the short name is displaying in admin on the list page
        """
        with less_console_noise():
            self.client.force_login(self.superuser)
            completed_domain_request()
            response = self.client.get("/admin/registrar/DomainRequest/")
            # There are 4 template references to Federal (4) plus two references in the table
            # for our actual application
            self.assertContains(response, "Federal", count=6)
            # This may be a bit more robust
            self.assertContains(response, '<td class="field-organization_type">Federal</td>', count=1)
            # Now let's make sure the long description does not exist
            self.assertNotContains(response, "Federal: an agency of the U.S. government")

    def transition_state_and_send_email(self, domain_request, status, rejection_reason=None):
        """Helper method for the email test cases."""

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            with less_console_noise():
                # Create a mock request
                request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(domain_request.pk))

                # Modify the domain request's properties
                domain_request.status = status
                domain_request.rejection_reason = rejection_reason

                # Use the model admin's save_model method
                self.admin.save_model(request, domain_request, form=None, change=True)

    def assert_email_is_accurate(
        self, expected_string, email_index, email_address, test_that_no_bcc=False, bcc_email_address=""
    ):
        """Helper method for the email test cases.
        email_index is the index of the email in mock_client."""

        with less_console_noise():
            # Access the arguments passed to send_email
            call_args = self.mock_client.EMAILS_SENT
            kwargs = call_args[email_index]["kwargs"]

            # Retrieve the email details from the arguments
            from_email = kwargs.get("FromEmailAddress")
            to_email = kwargs["Destination"]["ToAddresses"][0]
            email_content = kwargs["Content"]
            email_body = email_content["Simple"]["Body"]["Text"]["Data"]

            # Assert or perform other checks on the email details
            self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
            self.assertEqual(to_email, email_address)
            self.assertIn(expected_string, email_body)

        if test_that_no_bcc:
            _ = ""
            with self.assertRaises(KeyError):
                with less_console_noise():
                    _ = kwargs["Destination"]["BccAddresses"][0]
            self.assertEqual(_, "")

        if bcc_email_address:
            bcc_email = kwargs["Destination"]["BccAddresses"][0]
            self.assertEqual(bcc_email, bcc_email_address)

    def test_save_model_sends_submitted_email(self):
        """When transitioning to submitted from started or withdrawn on a domain request,
        an email is sent out.

        When transitioning to submitted from dns needed or in review on a domain request,
        no email is sent out.

        Also test that the default email set in settings is NOT BCCd on non-prod whenever
        an email does go out."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request()

            # Test Submitted Status from started
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 0, EMAIL, True)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assert_email_is_accurate(
                "Your .gov domain request has been withdrawn and will not be reviewed by our team.", 1, EMAIL, True
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (from withdrawn)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.IN_REVIEW)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in IN_REVIEW, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.IN_REVIEW)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to ACTION_NEEDED
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.ACTION_NEEDED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in ACTION_NEEDED, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    @override_settings(IS_PRODUCTION=True)
    def test_save_model_sends_submitted_email_with_bcc_on_prod(self):
        """When transitioning to submitted from started or withdrawn on a domain request,
        an email is sent out.

        When transitioning to submitted from dns needed or in review on a domain request,
        no email is sent out.

        Also test that the default email set in settings IS BCCd on prod whenever
        an email does go out."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            BCC_EMAIL = settings.DEFAULT_FROM_EMAIL

            # Create a sample application
            domain_request = completed_domain_request()

            # Test Submitted Status from started
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 0, EMAIL, False, BCC_EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assert_email_is_accurate(
                "Your .gov domain request has been withdrawn and will not be reviewed by our team.", 1, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (from withdrawn)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 0, EMAIL, False, BCC_EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.IN_REVIEW)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in IN_REVIEW, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.IN_REVIEW)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to ACTION_NEEDED
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.ACTION_NEEDED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in ACTION_NEEDED, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    def test_save_model_sends_approved_email(self):
        """When transitioning to approved on a domain request,
        an email is sent out every time."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Test Submitted Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 0, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(
                application,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.DOMAIN_PURPOSE,
            )
            self.assert_email_is_accurate("Your .gov domain request has been rejected.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (No new email should be sent)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    def test_save_model_sends_rejected_email_purpose_not_met(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is domain purpose."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason DOMAIN_PURPOSE and test email
            self.transition_state_and_send_email(
                application,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.DOMAIN_PURPOSE,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because the purpose you provided did not meet our \nrequirements.",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_requestor(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is requestor."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason REQUESTOR and test email including dynamic organization name
            self.transition_state_and_send_email(
                domain_request, DomainRequest.DomainRequestStatus.REJECTED, DomainRequest.RejectionReasons.REQUESTOR
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because we don’t believe you’re eligible to request a \n.gov "
                "domain on behalf of Testorg",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_org_has_domain(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is second domain."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason SECOND_DOMAIN_REASONING and test email including dynamic organization name
            self.transition_state_and_send_email(
                application,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.SECOND_DOMAIN_REASONING,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because Testorg has a .gov domain.", 0, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_contacts_or_org_legitimacy(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is contacts or org legitimacy."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason CONTACTS_OR_ORGANIZATION_LEGITIMACY and test email including dynamic organization name
            self.transition_state_and_send_email(
                application,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.CONTACTS_OR_ORGANIZATION_LEGITIMACY,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because we could not verify the organizational \n"
                "contacts you provided. If you have questions or comments, reply to this email.",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_org_eligibility(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is org eligibility."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason ORGANIZATION_ELIGIBILITY and test email including dynamic organization name
            self.transition_state_and_send_email(
                application,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.ORGANIZATION_ELIGIBILITY,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because we determined that Testorg is not \neligible for "
                "a .gov domain.",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_naming(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is naming."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason NAMING_REQUIREMENTS and test email including dynamic organization name
            self.transition_state_and_send_email(
                application,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.NAMING_REQUIREMENTS,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because it does not meet our naming requirements.", 0, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_other(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is other."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason NAMING_REQUIREMENTS and test email including dynamic organization name
            self.transition_state_and_send_email(
                application,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.OTHER,
            )
            self.assert_email_is_accurate("Choosing a .gov domain name", 0, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_transition_to_rejected_without_rejection_reason_does_trigger_error(self):
        """
        When transitioning to rejected without a rejection reason, admin throws a user friendly message.

        The transition fails.
        """

        with less_console_noise():
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)

            # Create a request object with a superuser
            request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(domain_request.pk))
            request.user = self.superuser

            with ExitStack() as stack:
                stack.enter_context(patch.object(messages, "error"))
                domain_request.status = DomainRequest.DomainRequestStatus.REJECTED

                self.admin.save_model(request, domain_request, None, True)

                messages.error.assert_called_once_with(
                    request,
                    "A rejection reason is required.",
                )

            domain_request.refresh_from_db()
            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.APPROVED)

    def test_transition_to_rejected_with_rejection_reason_does_not_trigger_error(self):
        """
        When transitioning to rejected with a rejection reason, admin does not throw an error alert.

        The transition is successful.
        """

        with less_console_noise():
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)

            # Create a request object with a superuser
            request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(domain_request.pk))
            request.user = self.superuser

            with ExitStack() as stack:
                stack.enter_context(patch.object(messages, "error"))
                domain_request.status = DomainRequest.DomainRequestStatus.REJECTED
                domain_request.rejection_reason = DomainRequest.RejectionReasons.CONTACTS_OR_ORGANIZATION_LEGITIMACY

                self.admin.save_model(request, domain_request, None, True)

                messages.error.assert_not_called()

            domain_request.refresh_from_db()
            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.REJECTED)

    def test_save_model_sends_withdrawn_email(self):
        """When transitioning to withdrawn on a domain request,
        an email is sent out every time."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Test Submitted Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assert_email_is_accurate(
                "Your .gov domain request has been withdrawn and will not be reviewed by our team.", 0, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (No new email should be sent)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    def test_save_model_sets_approved_domain(self):
        with less_console_noise():
            # make sure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Create a mock request
            request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(domain_request.pk))

            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                # Modify the domain request's property
                domain_request.status = DomainRequest.DomainRequestStatus.APPROVED

                # Use the model admin's save_model method
                self.admin.save_model(request, domain_request, form=None, change=True)

            # Test that approved domain exists and equals requested domain
            self.assertEqual(domain_request.requested_domain.name, domain_request.approved_domain.name)

    def test_save_model_sets_restricted_status_on_user(self):
        with less_console_noise():
            # make sure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample application
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Create a mock request
            request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(domain_request.pk))

            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                # Modify the domain request's property
                domain_request.status = DomainRequest.DomainRequestStatus.INELIGIBLE

                # Use the model admin's save_model method
                self.admin.save_model(request, domain_request, form=None, change=True)

            # Test that approved domain exists and equals requested domain
            self.assertEqual(domain_request.creator.status, "restricted")

    def test_readonly_when_restricted_creator(self):
        with less_console_noise():
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.creator.status = User.RESTRICTED
                domain_request.creator.save()

            request = self.factory.get("/")
            request.user = self.superuser

            readonly_fields = self.admin.get_readonly_fields(request, domain_request)

            expected_fields = [
                "id",
                "created_at",
                "updated_at",
                "status",
                "rejection_reason",
                "creator",
                "investigator",
                "organization_type",
                "federally_recognized_tribe",
                "state_recognized_tribe",
                "tribe_name",
                "federal_agency",
                "federal_type",
                "is_election_board",
                "organization_name",
                "address_line1",
                "address_line2",
                "city",
                "state_territory",
                "zipcode",
                "urbanization",
                "about_your_organization",
                "authorizing_official",
                "approved_domain",
                "requested_domain",
                "submitter",
                "purpose",
                "no_other_contacts_rationale",
                "anything_else",
                "is_policy_acknowledged",
                "submission_date",
                "notes",
                "current_websites",
                "other_contacts",
                "alternative_domains",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_fields_for_analyst(self):
        with less_console_noise():
            request = self.factory.get("/")  # Use the correct method and path
            request.user = self.staffuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = [
                "creator",
                "about_your_organization",
                "requested_domain",
                "approved_domain",
                "alternative_domains",
                "purpose",
                "submitter",
                "no_other_contacts_rationale",
                "anything_else",
                "is_policy_acknowledged",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_fields_for_superuser(self):
        with less_console_noise():
            request = self.factory.get("/")  # Use the correct method and path
            request.user = self.superuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = []

            self.assertEqual(readonly_fields, expected_fields)

    def test_saving_when_restricted_creator(self):
        with less_console_noise():
            # Create an instance of the model
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.creator.status = User.RESTRICTED
                domain_request.creator.save()

            # Create a request object with a superuser
            request = self.factory.get("/")
            request.user = self.superuser

            with patch("django.contrib.messages.error") as mock_error:
                # Simulate saving the model
                self.admin.save_model(request, domain_request, None, False)

                # Assert that the error message was called with the correct argument
                mock_error.assert_called_once_with(
                    request,
                    "This action is not permitted for applications with a restricted creator.",
                )

            # Assert that the status has not changed
            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.IN_REVIEW)

    def test_change_view_with_restricted_creator(self):
        with less_console_noise():
            # Create an instance of the model
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.creator.status = User.RESTRICTED
                domain_request.creator.save()

            with patch("django.contrib.messages.warning") as mock_warning:
                # Create a request object with a superuser
                request = self.factory.get("/admin/your_app/DomainRequest/{}/change/".format(domain_request.pk))
                request.user = self.superuser

                self.admin.display_restricted_warning(request, domain_request)

                # Assert that the error message was called with the correct argument
                mock_warning.assert_called_once_with(
                    request,
                    "Cannot edit a domain request with a restricted creator.",
                )

    def trigger_saving_approved_to_another_state(self, domain_is_active, another_state, rejection_reason=None):
        """Helper method that triggers domain request state changes from approved to another state,
        with an associated domain that can be either active (READY) or not.

        Used to test errors when saving a change with an active domain, also used to test side effects
        when saving a change goes through."""

        with less_console_noise():
            # Create an instance of the model
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)
            domain = Domain.objects.create(name=domain_request.requested_domain.name)
            domain_information = DomainInformation.objects.create(creator=self.superuser, domain=domain)
            domain_request.approved_domain = domain
            domain_request.save()

            # Create a request object with a superuser
            request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(domain_request.pk))
            request.user = self.superuser

            # Define a custom implementation for is_active
            def custom_is_active(self):
                return domain_is_active  # Override to return True

            # Use ExitStack to combine patch contexts
            with ExitStack() as stack:
                # Patch Domain.is_active and django.contrib.messages.error simultaneously
                stack.enter_context(patch.object(Domain, "is_active", custom_is_active))
                stack.enter_context(patch.object(messages, "error"))

                domain_request.status = another_state
                domain_request.rejection_reason = rejection_reason

                self.admin.save_model(request, domain_request, None, True)

                # Assert that the error message was called with the correct argument
                if domain_is_active:
                    messages.error.assert_called_once_with(
                        request,
                        "This action is not permitted. The domain " + "is already active.",
                    )
                else:
                    # Assert that the error message was never called
                    messages.error.assert_not_called()

                    self.assertEqual(domain_request.approved_domain, None)

                    # Assert that Domain got Deleted
                    with self.assertRaises(Domain.DoesNotExist):
                        domain.refresh_from_db()

                    # Assert that DomainInformation got Deleted
                    with self.assertRaises(DomainInformation.DoesNotExist):
                        domain_information.refresh_from_db()

    def test_error_when_saving_approved_to_in_review_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.IN_REVIEW)

    def test_error_when_saving_approved_to_action_needed_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.ACTION_NEEDED)

    def test_error_when_saving_approved_to_rejected_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.REJECTED)

    def test_error_when_saving_approved_to_ineligible_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.INELIGIBLE)

    def test_side_effects_when_saving_approved_to_in_review(self):
        self.trigger_saving_approved_to_another_state(False, DomainRequest.DomainRequestStatus.IN_REVIEW)

    def test_side_effects_when_saving_approved_to_action_needed(self):
        self.trigger_saving_approved_to_another_state(False, DomainRequest.DomainRequestStatus.ACTION_NEEDED)

    def test_side_effects_when_saving_approved_to_rejected(self):
        self.trigger_saving_approved_to_another_state(
            False,
            DomainRequest.DomainRequestStatus.REJECTED,
            DomainRequest.RejectionReasons.CONTACTS_OR_ORGANIZATION_LEGITIMACY,
        )

    def test_side_effects_when_saving_approved_to_ineligible(self):
        self.trigger_saving_approved_to_another_state(False, DomainRequest.DomainRequestStatus.INELIGIBLE)

    def test_has_correct_filters(self):
        """
        This test verifies that DomainRequestAdmin has the correct filters set up.

        It retrieves the current list of filters from DomainRequestAdmin
        and checks that it matches the expected list of filters.
        """
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.superuser

            # Grab the current list of table filters
            readonly_fields = self.admin.get_list_filter(request)
            expected_fields = (
                "status",
                "organization_type",
                "federal_type",
                DomainRequestAdmin.ElectionOfficeFilter,
                "rejection_reason",
                DomainRequestAdmin.InvestigatorFilter,
            )

            self.assertEqual(readonly_fields, expected_fields)

    def test_table_sorted_alphabetically(self):
        """
        This test verifies that the DomainRequestAdmin table is sorted alphabetically
        by the 'requested_domain__name' field.

        It creates a list of DomainRequest instances in a non-alphabetical order,
        then retrieves the queryset from the DomainRequestAdmin and checks
        that it matches the expected queryset,
        which is sorted alphabetically by the 'requested_domain__name' field.
        """
        with less_console_noise():
            # Creates a list of DomainRequests in scrambled order
            multiple_unalphabetical_domain_objects("domain_request")

            request = self.factory.get("/")
            request.user = self.superuser

            # Get the expected list of alphabetically sorted DomainRequests
            expected_order = DomainRequest.objects.order_by("requested_domain__name")

            # Get the returned queryset
            queryset = self.admin.get_queryset(request)

            # Check the order
            self.assertEqual(
                list(queryset),
                list(expected_order),
            )

    def test_displays_investigator_filter(self):
        """
        This test verifies that the investigator filter in the admin interface for
        the DomainRequest model displays correctly.

        It creates two DomainRequest instances, each with a different investigator.
        It then simulates a staff user logging in and applying the investigator filter
        on the DomainRequest admin page.

        We then test if the page displays the filter we expect, but we do not test
        if we get back the correct response in the table. This is to isolate if
        the filter displays correctly, when the filter isn't filtering correctly.
        """

        with less_console_noise():
            # Create a mock DomainRequest object, with a fake investigator
            application: DomainRequest = generic_domain_object("domain_request", "SomeGuy")
            investigator_user = User.objects.filter(username=domain_request.investigator.username).get()
            investigator_user.is_staff = True
            investigator_user.save()

            p = "userpass"
            self.client.login(username="staffuser", password=p)
            response = self.client.get(
                "/admin/registrar/DomainRequest/",
                {
                    "investigator__id__exact": investigator_user.id,
                },
                follow=True,
            )

            # Then, test if the filter actually exists
            self.assertIn("filters", response.context)

            # Assert the content of filters and search_query
            filters = response.context["filters"]

            self.assertEqual(
                filters,
                [
                    {
                        "parameter_name": "investigator",
                        "parameter_value": "SomeGuy first_name:investigator SomeGuy last_name:investigator",
                    },
                ],
            )

    def test_investigator_dropdown_displays_only_staff(self):
        """
        This test verifies that the dropdown for the 'investigator' field in the DomainRequestAdmin
        interface only displays users who are marked as staff.

        It creates two DomainRequest instances, one with an investigator
        who is a staff user and another with an investigator who is not a staff user.

        It then retrieves the queryset for the 'investigator' dropdown from DomainRequestAdmin
        and checks that it matches the expected queryset, which only includes staff users.
        """

        with less_console_noise():
            # Create a mock DomainRequest object, with a fake investigator
            application: DomainRequest = generic_domain_object("domain_request", "SomeGuy")
            investigator_user = User.objects.filter(username=domain_request.investigator.username).get()
            investigator_user.is_staff = True
            investigator_user.save()

            # Create a mock DomainRequest object, with a user that is not staff
            domain_request_2: DomainRequest = generic_domain_object("domain_request", "SomeOtherGuy")
            investigator_user_2 = User.objects.filter(username=domain_request_2.investigator.username).get()
            investigator_user_2.is_staff = False
            investigator_user_2.save()

            p = "userpass"
            self.client.login(username="staffuser", password=p)

            request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(domain_request.pk))

            # Get the actual field from the model's meta information
            investigator_field = DomainRequest._meta.get_field("investigator")

            # We should only be displaying staff users, in alphabetical order
            sorted_fields = ["first_name", "last_name", "email"]
            expected_dropdown = list(User.objects.filter(is_staff=True).order_by(*sorted_fields))

            # Grab the current dropdown. We do an API call to autocomplete to get this info.
            domain_request_queryset = self.admin.formfield_for_foreignkey(investigator_field, request).queryset
            user_request = self.factory.post(
                "/admin/autocomplete/?app_label=registrar&model_name=DomainRequest&field_name=investigator"
            )
            user_admin = MyUserAdmin(User, self.site)
            user_queryset = user_admin.get_search_results(user_request, domain_request_queryset, None)[0]
            current_dropdown = list(user_queryset)

            self.assertEqual(expected_dropdown, current_dropdown)

            # Non staff users should not be in the list
            self.assertNotIn(domain_request_2, current_dropdown)

    def test_investigator_list_is_alphabetically_sorted(self):
        """
        This test verifies that filter list for the 'investigator'
        is displayed alphabetically
        """
        with less_console_noise():
            # Create a mock DomainRequest object, with a fake investigator
            application: DomainRequest = generic_domain_object("domain_request", "SomeGuy")
            investigator_user = User.objects.filter(username=domain_request.investigator.username).get()
            investigator_user.is_staff = True
            investigator_user.save()

            domain_request_2: DomainRequest = generic_domain_object("domain_request", "AGuy")
            investigator_user_2 = User.objects.filter(username=domain_request_2.investigator.username).get()
            investigator_user_2.first_name = "AGuy"
            investigator_user_2.is_staff = True
            investigator_user_2.save()

            domain_request_3: DomainRequest = generic_domain_object("domain_request", "FinalGuy")
            investigator_user_3 = User.objects.filter(username=domain_request_3.investigator.username).get()
            investigator_user_3.first_name = "FinalGuy"
            investigator_user_3.is_staff = True
            investigator_user_3.save()

            p = "userpass"
            self.client.login(username="staffuser", password=p)
            request = RequestFactory().get("/")

            # These names have metadata embedded in them. :investigator implicitly tests if
            # these are actually from the attribute "investigator".
            expected_list = [
                "AGuy AGuy last_name:investigator",
                "FinalGuy FinalGuy last_name:investigator",
                "SomeGuy first_name:investigator SomeGuy last_name:investigator",
            ]

            # Get the actual sorted list of investigators from the lookups method
            actual_list = [item for _, item in self.admin.InvestigatorFilter.lookups(self, request, self.admin)]

            self.assertEqual(expected_list, actual_list)

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()
        Website.objects.all().delete()
        self.mock_client.EMAILS_SENT.clear()


class DomainInvitationAdminTest(TestCase):
    """Tests for the DomainInvitation page"""

    def setUp(self):
        """Create a client object"""
        self.client = Client(HTTP_HOST="localhost:8080")
        self.factory = RequestFactory()
        self.admin = ListHeaderAdmin(model=DomainInvitationAdmin, admin_site=AdminSite())
        self.superuser = create_superuser()

    def tearDown(self):
        """Delete all DomainInvitation objects"""
        DomainInvitation.objects.all().delete()

    def test_get_filters(self):
        """Ensures that our filters are displaying correctly"""
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            response = self.client.get(
                "/admin/registrar/domaininvitation/",
                {},
                follow=True,
            )

            # Assert that the filters are added
            self.assertContains(response, "invited", count=2)
            self.assertContains(response, "Invited", count=2)
            self.assertContains(response, "retrieved", count=2)
            self.assertContains(response, "Retrieved", count=2)

            # Check for the HTML context specificially
            invited_html = '<a href="?status__exact=invited">Invited</a>'
            retrieved_html = '<a href="?status__exact=retrieved">Retrieved</a>'

            self.assertContains(response, invited_html, count=1)
            self.assertContains(response, retrieved_html, count=1)


class TestDomainInformationAdmin(TestCase):
    def setUp(self):
        """Setup environment for a mock admin user"""
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = DomainInformationAdmin(model=DomainInformation, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.mock_data_generator = AuditedAdminMockData()

        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/DomainInformation/",
            model=DomainInformation,
        )

        # Create fake DomainInformation objects
        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Apple"),
            submitter=self.mock_data_generator.dummy_contact("Zebra", "submitter"),
        )

        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Zebra"),
            submitter=self.mock_data_generator.dummy_contact("Apple", "submitter"),
        )

        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Circus"),
            submitter=self.mock_data_generator.dummy_contact("Xylophone", "submitter"),
        )

        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Xylophone"),
            submitter=self.mock_data_generator.dummy_contact("Circus", "submitter"),
        )

    def tearDown(self):
        """Delete all Users, Domains, and UserDomainRoles"""
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Domain.objects.all().delete()
        Contact.objects.all().delete()
        User.objects.all().delete()

    def test_readonly_fields_for_analyst(self):
        """Ensures that analysts have their permissions setup correctly"""
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.staffuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = [
                "creator",
                "type_of_work",
                "more_organization_information",
                "domain",
                "domain_request",
                "submitter",
                "no_other_contacts_rationale",
                "anything_else",
                "is_policy_acknowledged",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_domain_sortable(self):
        """Tests if DomainInformation sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("1", ("domain__name",))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-1", ("-domain__name",))

    def test_submitter_sortable(self):
        """Tests if DomainInformation sorts by submitter correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted(
                "4",
                ("submitter__first_name", "submitter__last_name"),
            )

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-4", ("-submitter__first_name", "-submitter__last_name"))


class UserDomainRoleAdminTest(TestCase):
    def setUp(self):
        """Setup environment for a mock admin user"""
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = UserDomainRoleAdmin(model=UserDomainRole, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/UserDomainRole/",
            model=UserDomainRole,
        )

    def tearDown(self):
        """Delete all Users, Domains, and UserDomainRoles"""
        User.objects.all().delete()
        Domain.objects.all().delete()
        UserDomainRole.objects.all().delete()

    def test_domain_sortable(self):
        """Tests if the UserDomainrole sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            fake_user = User.objects.create(
                username="dummyuser", first_name="Stewart", last_name="Jones", email="AntarcticPolarBears@example.com"
            )

            # Create a list of UserDomainRoles that are in random order
            mocks_to_create = ["jkl.gov", "ghi.gov", "abc.gov", "def.gov"]
            for name in mocks_to_create:
                fake_domain = Domain.objects.create(name=name)
                UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("2", ("domain__name",))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-2", ("-domain__name",))

    def test_user_sortable(self):
        """Tests if the UserDomainrole sorts by user correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            mock_data_generator = AuditedAdminMockData()

            fake_domain = Domain.objects.create(name="igorville.gov")
            # Create a list of UserDomainRoles that are in random order
            mocks_to_create = ["jkl", "ghi", "abc", "def"]
            for name in mocks_to_create:
                # Creates a fake "User" object
                fake_user = mock_data_generator.dummy_user(name, "user")
                UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("1", ("user__first_name", "user__last_name"))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-1", ("-user__first_name", "-user__last_name"))

    def test_email_not_in_search(self):
        """Tests the search bar in Django Admin for UserDomainRoleAdmin.
        Should return no results for an invalid email."""
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            fake_user = User.objects.create(
                username="dummyuser", first_name="Stewart", last_name="Jones", email="AntarcticPolarBears@example.com"
            )
            fake_domain = Domain.objects.create(name="test123")
            UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")
            # Make the request using the Client class
            # which handles CSRF
            # Follow=True handles the redirect
            response = self.client.get(
                "/admin/registrar/userdomainrole/",
                {
                    "q": "testmail@igorville.com",
                },
                follow=True,
            )

            # Assert that the query is added to the extra_context
            self.assertIn("search_query", response.context)
            # Assert the content of filters and search_query
            search_query = response.context["search_query"]
            self.assertEqual(search_query, "testmail@igorville.com")

            # We only need to check for the end of the HTML string
            self.assertNotContains(response, "Stewart Jones AntarcticPolarBears@example.com</a></th>")

    def test_email_in_search(self):
        """Tests the search bar in Django Admin for UserDomainRoleAdmin.
        Should return results for an valid email."""
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            fake_user = User.objects.create(
                username="dummyuser", first_name="Joe", last_name="Jones", email="AntarcticPolarBears@example.com"
            )
            fake_domain = Domain.objects.create(name="fake")
            UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")
            # Make the request using the Client class
            # which handles CSRF
            # Follow=True handles the redirect
            response = self.client.get(
                "/admin/registrar/userdomainrole/",
                {
                    "q": "AntarcticPolarBears@example.com",
                },
                follow=True,
            )

            # Assert that the query is added to the extra_context
            self.assertIn("search_query", response.context)

            search_query = response.context["search_query"]
            self.assertEqual(search_query, "AntarcticPolarBears@example.com")

            # We only need to check for the end of the HTML string
            self.assertContains(response, "Joe Jones AntarcticPolarBears@example.com</a></th>", count=1)


class ListHeaderAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = ListHeaderAdmin(model=DomainRequest, admin_site=None)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()

    def test_changelist_view(self):
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)
            # Mock a user
            user = mock_user()
            # Make the request using the Client class
            # which handles CSRF
            # Follow=True handles the redirect
            response = self.client.get(
                "/admin/registrar/DomainRequest/",
                {
                    "status__exact": "started",
                    "investigator__id__exact": user.id,
                    "q": "Hello",
                },
                follow=True,
            )
            # Assert that the filters and search_query are added to the extra_context
            self.assertIn("filters", response.context)
            self.assertIn("search_query", response.context)
            # Assert the content of filters and search_query
            filters = response.context["filters"]
            search_query = response.context["search_query"]
            self.assertEqual(search_query, "Hello")
            self.assertEqual(
                filters,
                [
                    {"parameter_name": "status", "parameter_value": "started"},
                    {
                        "parameter_name": "investigator",
                        "parameter_value": user.first_name + " " + user.last_name,
                    },
                ],
            )

    def test_get_filters(self):
        with less_console_noise():
            # Create a mock request object
            request = self.factory.get("/admin/yourmodel/")
            # Set the GET parameters for testing
            request.GET = {
                "status": "started",
                "investigator": "Jeff Lebowski",
                "q": "search_value",
            }
            # Call the get_filters method
            filters = self.admin.get_filters(request)
            # Assert the filters extracted from the request GET
            self.assertEqual(
                filters,
                [
                    {"parameter_name": "status", "parameter_value": "started"},
                    {"parameter_name": "investigator", "parameter_value": "Jeff Lebowski"},
                ],
            )

    def tearDown(self):
        # delete any applications too
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()


class MyUserAdminTest(TestCase):
    def setUp(self):
        admin_site = AdminSite()
        self.admin = MyUserAdmin(model=get_user_model(), admin_site=admin_site)

    def test_list_display_without_username(self):
        with less_console_noise():
            request = self.client.request().wsgi_request
            request.user = create_user()

            list_display = self.admin.get_list_display(request)
            expected_list_display = [
                "email",
                "first_name",
                "last_name",
                "group",
                "status",
            ]

            self.assertEqual(list_display, expected_list_display)
            self.assertNotIn("username", list_display)

    def test_get_fieldsets_superuser(self):
        with less_console_noise():
            request = self.client.request().wsgi_request
            request.user = create_superuser()
            fieldsets = self.admin.get_fieldsets(request)
            expected_fieldsets = super(MyUserAdmin, self.admin).get_fieldsets(request)
            self.assertEqual(fieldsets, expected_fieldsets)

    def test_get_fieldsets_cisa_analyst(self):
        with less_console_noise():
            request = self.client.request().wsgi_request
            request.user = create_user()
            fieldsets = self.admin.get_fieldsets(request)
            expected_fieldsets = (
                (None, {"fields": ("password", "status")}),
                ("Personal Info", {"fields": ("first_name", "last_name", "email")}),
                ("Permissions", {"fields": ("is_active", "groups")}),
                ("Important dates", {"fields": ("last_login", "date_joined")}),
            )
            self.assertEqual(fieldsets, expected_fieldsets)

    def tearDown(self):
        User.objects.all().delete()


class AuditedAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")

    def order_by_desired_field_helper(self, obj_to_sort: AuditedAdmin, request, field_name, *obj_names):
        with less_console_noise():
            formatted_sort_fields = []
            for obj in obj_names:
                formatted_sort_fields.append("{}__{}".format(field_name, obj))

            ordered_list = list(
                obj_to_sort.get_queryset(request).order_by(*formatted_sort_fields).values_list(*formatted_sort_fields)
            )

            return ordered_list

    def test_alphabetically_sorted_domain_request_investigator(self):
        """Tests if the investigator field is alphabetically sorted by mimicking
        the call event flow"""
        # Creates multiple domain requests - review status does not matter
        applications = multiple_unalphabetical_domain_objects("domain_request")

        # Create a mock request
        domain_request_request = self.factory.post(
            "/admin/registrar/DomainRequest/{}/change/".format(applications[0].pk)
        )

        # Get the formfield data from the domain request page
        domain_request_admin = AuditedAdmin(DomainRequest, self.site)
        field = DomainRequest.investigator.field
        domain_request_queryset = domain_request_admin.formfield_for_foreignkey(field, domain_request_request).queryset

        request = self.factory.post(
            "/admin/autocomplete/?app_label=registrar&model_name=DomainRequest&field_name=investigator"
        )

        sorted_fields = ["first_name", "last_name", "email"]
        desired_sort_order = list(User.objects.filter(is_staff=True).order_by(*sorted_fields))

        # Grab the data returned from get search results
        admin = MyUserAdmin(User, self.site)
        search_queryset = admin.get_search_results(request, domain_request_queryset, None)[0]
        current_sort_order = list(search_queryset)

        self.assertEqual(
            desired_sort_order,
            current_sort_order,
            "Investigator is not ordered alphabetically",
        )

    # This test case should be refactored in general, as it is too overly specific and engineered
    def test_alphabetically_sorted_fk_fields_domain_request(self):
        with less_console_noise():
            tested_fields = [
                DomainRequest.authorizing_official.field,
                DomainRequest.submitter.field,
                # DomainRequest.investigator.field,
                DomainRequest.creator.field,
                DomainRequest.requested_domain.field,
            ]

            # Creates multiple domain requests - review status does not matter
            applications = multiple_unalphabetical_domain_objects("domain_request")

            # Create a mock request
            request = self.factory.post("/admin/registrar/DomainRequest/{}/change/".format(applications[0].pk))

            model_admin = AuditedAdmin(DomainRequest, self.site)

            sorted_fields = []
            # Typically we wouldn't want two nested for fields,
            # but both fields are of a fixed length.
            # For test case purposes, this should be performant.
            for field in tested_fields:
                with self.subTest(field=field):
                    isNamefield: bool = field == DomainRequest.requested_domain.field
                    if isNamefield:
                        sorted_fields = ["name"]
                    else:
                        sorted_fields = ["first_name", "last_name"]
                    # We want both of these to be lists, as it is richer test wise.

                    desired_order = self.order_by_desired_field_helper(model_admin, request, field.name, *sorted_fields)
                    current_sort_order = list(model_admin.formfield_for_foreignkey(field, request).queryset)

                    # Conforms to the same object structure as desired_order
                    current_sort_order_coerced_type = []

                    # This is necessary as .queryset and get_queryset
                    # return lists of different types/structures.
                    # We need to parse this data and coerce them into the same type.
                    for contact in current_sort_order:
                        if not isNamefield:
                            first = contact.first_name
                            last = contact.last_name
                        else:
                            first = contact.name
                            last = None

                        name_tuple = self.coerced_fk_field_helper(first, last, field.name, ":")
                        if name_tuple is not None:
                            current_sort_order_coerced_type.append(name_tuple)

                    self.assertEqual(
                        desired_order,
                        current_sort_order_coerced_type,
                        "{} is not ordered alphabetically".format(field.name),
                    )

    def test_alphabetically_sorted_fk_fields_domain_information(self):
        with less_console_noise():
            tested_fields = [
                DomainInformation.authorizing_official.field,
                DomainInformation.submitter.field,
                # DomainInformation.creator.field,
                (DomainInformation.domain.field, ["name"]),
                (DomainInformation.domain_request.field, ["requested_domain__name"]),
            ]
            # Creates multiple domain requests - review status does not matter
            applications = multiple_unalphabetical_domain_objects("information")

            # Create a mock request
            request = self.factory.post("/admin/registrar/domaininformation/{}/change/".format(applications[0].pk))

            model_admin = AuditedAdmin(DomainInformation, self.site)

            sorted_fields = []
            # Typically we wouldn't want two nested for fields,
            # but both fields are of a fixed length.
            # For test case purposes, this should be performant.
            for field in tested_fields:
                isOtherOrderfield: bool = isinstance(field, tuple)
                field_obj = None
                if isOtherOrderfield:
                    sorted_fields = field[1]
                    field_obj = field[0]
                else:
                    sorted_fields = ["first_name", "last_name"]
                    field_obj = field
                # We want both of these to be lists, as it is richer test wise.
                desired_order = self.order_by_desired_field_helper(model_admin, request, field_obj.name, *sorted_fields)
                current_sort_order = list(model_admin.formfield_for_foreignkey(field_obj, request).queryset)

                # Conforms to the same object structure as desired_order
                current_sort_order_coerced_type = []

                # This is necessary as .queryset and get_queryset
                # return lists of different types/structures.
                # We need to parse this data and coerce them into the same type.
                for obj in current_sort_order:
                    last = None
                    if not isOtherOrderfield:
                        first = obj.first_name
                        last = obj.last_name
                    elif field_obj == DomainInformation.domain.field:
                        first = obj.name
                    elif field_obj == DomainInformation.domain_request.field:
                        first = obj.requested_domain.name

                    name_tuple = self.coerced_fk_field_helper(first, last, field_obj.name, ":")
                    if name_tuple is not None:
                        current_sort_order_coerced_type.append(name_tuple)

                self.assertEqual(
                    desired_order,
                    current_sort_order_coerced_type,
                    "{} is not ordered alphabetically".format(field_obj.name),
                )

    def test_alphabetically_sorted_fk_fields_domain_invitation(self):
        with less_console_noise():
            tested_fields = [DomainInvitation.domain.field]

            # Creates multiple domain requests - review status does not matter
            applications = multiple_unalphabetical_domain_objects("invitation")

            # Create a mock request
            request = self.factory.post("/admin/registrar/domaininvitation/{}/change/".format(applications[0].pk))

            model_admin = AuditedAdmin(DomainInvitation, self.site)

            sorted_fields = []
            # Typically we wouldn't want two nested for fields,
            # but both fields are of a fixed length.
            # For test case purposes, this should be performant.
            for field in tested_fields:
                sorted_fields = ["name"]
                # We want both of these to be lists, as it is richer test wise.

                desired_order = self.order_by_desired_field_helper(model_admin, request, field.name, *sorted_fields)
                current_sort_order = list(model_admin.formfield_for_foreignkey(field, request).queryset)

                # Conforms to the same object structure as desired_order
                current_sort_order_coerced_type = []

                # This is necessary as .queryset and get_queryset
                # return lists of different types/structures.
                # We need to parse this data and coerce them into the same type.
                for contact in current_sort_order:
                    first = contact.name
                    last = None

                    name_tuple = self.coerced_fk_field_helper(first, last, field.name, ":")
                    if name_tuple is not None:
                        current_sort_order_coerced_type.append(name_tuple)

                self.assertEqual(
                    desired_order,
                    current_sort_order_coerced_type,
                    "{} is not ordered alphabetically".format(field.name),
                )

    def coerced_fk_field_helper(self, first_name, last_name, field_name, queryset_shorthand):
        """Handles edge cases for test cases"""
        if first_name is None:
            raise ValueError("Invalid value for first_name, must be defined")

        returned_tuple = (first_name, last_name)
        # Handles edge case for names - structured strangely
        if last_name is None:
            return (first_name,)

        if first_name.split(queryset_shorthand)[1] == field_name:
            return returned_tuple
        else:
            return None

    def tearDown(self):
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInvitation.objects.all().delete()


class DomainSessionVariableTest(TestCase):
    """Test cases for session variables in Django Admin"""

    def setUp(self):
        self.factory = RequestFactory()
        self.admin = DomainAdmin(Domain, None)
        self.client = Client(HTTP_HOST="localhost:8080")

    def test_session_vars_set_correctly(self):
        """Checks if session variables are being set correctly"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information = generic_domain_object("information", "session")
            request = self.get_factory_post_edit_domain(dummy_domain_information.domain.pk)
            self.populate_session_values(request, dummy_domain_information.domain)
            self.assertEqual(request.session["analyst_action"], "edit")
            self.assertEqual(
                request.session["analyst_action_location"],
                dummy_domain_information.domain.pk,
            )

    def test_session_vars_set_correctly_hardcoded_domain(self):
        """Checks if session variables are being set correctly"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information: Domain = generic_domain_object("information", "session")
            dummy_domain_information.domain.pk = 1

            request = self.get_factory_post_edit_domain(dummy_domain_information.domain.pk)
            self.populate_session_values(request, dummy_domain_information.domain)
            self.assertEqual(request.session["analyst_action"], "edit")
            self.assertEqual(request.session["analyst_action_location"], 1)

    def test_session_variables_reset_correctly(self):
        """Checks if incorrect session variables get overridden"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information = generic_domain_object("information", "session")
            request = self.get_factory_post_edit_domain(dummy_domain_information.domain.pk)

            self.populate_session_values(request, dummy_domain_information.domain, preload_bad_data=True)

            self.assertEqual(request.session["analyst_action"], "edit")
            self.assertEqual(
                request.session["analyst_action_location"],
                dummy_domain_information.domain.pk,
            )

    def test_session_variables_retain_information(self):
        """Checks to see if session variables retain old information"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information_list = multiple_unalphabetical_domain_objects("information")
            for item in dummy_domain_information_list:
                request = self.get_factory_post_edit_domain(item.domain.pk)
                self.populate_session_values(request, item.domain)

                self.assertEqual(request.session["analyst_action"], "edit")
                self.assertEqual(request.session["analyst_action_location"], item.domain.pk)

    def test_session_variables_concurrent_requests(self):
        """Simulates two requests at once"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            info_first = generic_domain_object("information", "session")
            info_second = generic_domain_object("information", "session2")

            request_first = self.get_factory_post_edit_domain(info_first.domain.pk)
            request_second = self.get_factory_post_edit_domain(info_second.domain.pk)

            self.populate_session_values(request_first, info_first.domain, True)
            self.populate_session_values(request_second, info_second.domain, True)

            # Check if anything got nulled out
            self.assertNotEqual(request_first.session["analyst_action"], None)
            self.assertNotEqual(request_second.session["analyst_action"], None)
            self.assertNotEqual(request_first.session["analyst_action_location"], None)
            self.assertNotEqual(request_second.session["analyst_action_location"], None)

            # Check if they are both the same action 'type'
            self.assertEqual(request_first.session["analyst_action"], "edit")
            self.assertEqual(request_second.session["analyst_action"], "edit")

            # Check their locations, and ensure they aren't the same across both
            self.assertNotEqual(
                request_first.session["analyst_action_location"],
                request_second.session["analyst_action_location"],
            )

    def populate_session_values(self, request, domain_object, preload_bad_data=False):
        """Boilerplate for creating mock sessions"""
        request.user = self.client
        request.session = SessionStore()
        request.session.create()
        if preload_bad_data:
            request.session["analyst_action"] = "invalid"
            request.session["analyst_action_location"] = "bad location"
        self.admin.response_change(request, domain_object)

    def get_factory_post_edit_domain(self, primary_key):
        """Posts to registrar domain change
        with the edit domain button 'clicked',
        then returns the factory object"""
        return self.factory.post(
            reverse("admin:registrar_domain_change", args=(primary_key,)),
            {"_edit_domain": "true"},
            follow=True,
        )


class ContactAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.admin = ContactAdmin(model=get_user_model(), admin_site=None)
        self.superuser = create_superuser()
        self.staffuser = create_user()

    def test_readonly_when_restricted_staffuser(self):
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.staffuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = [
                "user",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_when_restricted_superuser(self):
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.superuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = []

            self.assertEqual(readonly_fields, expected_fields)

    def test_change_view_for_joined_contact_five_or_less(self):
        """Create a contact, join it to 4 domain requests. The 5th join will be a user.
        Assert that the warning on the contact form lists 5 joins."""
        with less_console_noise():
            self.client.force_login(self.superuser)

            # Create an instance of the model
            contact, _ = Contact.objects.get_or_create(user=self.staffuser)

            # join it to 4 domain requests. The 5th join will be a user.
            application1 = completed_domain_request(submitter=contact, name="city1.gov")
            application2 = completed_domain_request(submitter=contact, name="city2.gov")
            application3 = completed_domain_request(submitter=contact, name="city3.gov")
            application4 = completed_domain_request(submitter=contact, name="city4.gov")

            with patch("django.contrib.messages.warning") as mock_warning:
                # Use the test client to simulate the request
                response = self.client.get(reverse("admin:registrar_contact_change", args=[contact.pk]))

                # Assert that the error message was called with the correct argument
                # Note: The 5th join will be a user.
                mock_warning.assert_called_once_with(
                    response.wsgi_request,
                    "<ul class='messagelist_content-list--unstyled'>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application1.pk}/change/'>city1.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application2.pk}/change/'>city2.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application3.pk}/change/'>city3.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application4.pk}/change/'>city4.gov</a></li>"
                    "<li>Joined to User: <a href='/admin/registrar/"
                    f"user/{self.staffuser.pk}/change/'>staff@example.com</a></li>"
                    "</ul>",
                )

    def test_change_view_for_joined_contact_five_or_more(self):
        """Create a contact, join it to 5 domain requests. The 6th join will be a user.
        Assert that the warning on the contact form lists 5 joins and a '1 more' ellispsis."""
        with less_console_noise():
            self.client.force_login(self.superuser)
            # Create an instance of the model
            # join it to 5 domain requests. The 6th join will be a user.
            contact, _ = Contact.objects.get_or_create(user=self.staffuser)
            application1 = completed_domain_request(submitter=contact, name="city1.gov")
            application2 = completed_domain_request(submitter=contact, name="city2.gov")
            application3 = completed_domain_request(submitter=contact, name="city3.gov")
            application4 = completed_domain_request(submitter=contact, name="city4.gov")
            application5 = completed_domain_request(submitter=contact, name="city5.gov")
            with patch("django.contrib.messages.warning") as mock_warning:
                # Use the test client to simulate the request
                response = self.client.get(reverse("admin:registrar_contact_change", args=[contact.pk]))
                logger.debug(mock_warning)
                # Assert that the error message was called with the correct argument
                # Note: The 6th join will be a user.
                mock_warning.assert_called_once_with(
                    response.wsgi_request,
                    "<ul class='messagelist_content-list--unstyled'>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application1.pk}/change/'>city1.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application2.pk}/change/'>city2.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application3.pk}/change/'>city3.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application4.pk}/change/'>city4.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"DomainRequest/{application5.pk}/change/'>city5.gov</a></li>"
                    "</ul>"
                    "<p class='font-sans-3xs'>And 1 more...</p>",
                )

    def tearDown(self):
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()
        User.objects.all().delete()


class VerifiedByStaffAdminTestCase(TestCase):
    def setUp(self):
        self.superuser = create_superuser()
        self.factory = RequestFactory()

    def test_save_model_sets_user_field(self):
        with less_console_noise():
            self.client.force_login(self.superuser)

            # Create an instance of the admin class
            admin_instance = VerifiedByStaffAdmin(model=VerifiedByStaff, admin_site=None)

            # Create a VerifiedByStaff instance
            vip_instance = VerifiedByStaff(email="test@example.com", notes="Test Notes")

            # Create a request object
            request = self.factory.post("/admin/yourapp/VerifiedByStaff/add/")
            request.user = self.superuser

            # Call the save_model method
            admin_instance.save_model(request, vip_instance, None, None)

            # Check that the user field is set to the request.user
            self.assertEqual(vip_instance.requestor, self.superuser)
