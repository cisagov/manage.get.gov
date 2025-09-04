from django.test import TestCase
from django.db.utils import IntegrityError
from django.db import transaction
from unittest.mock import patch


from registrar.models import (
    Contact,
    DomainRequest,
    DomainInformation,
    User,
    Website,
    Domain,
    DraftDomain,
    FederalAgency,
    AllowedEmail,
    Portfolio,
    Suborganization,
    UserPortfolioPermission,
)
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices

import boto3_mocking
from registrar.utility.constants import BranchChoices
from registrar.utility.errors import FSMDomainRequestError

from .common import (
    MockSESClient,
    create_user,
    create_superuser,
    less_console_noise,
    completed_domain_request,
    set_domain_request_investigators,
)
from django_fsm import TransitionNotAllowed

from api.tests.common import less_console_noise_decorator


@boto3_mocking.patching
class TestDomainRequest(TestCase):
    @less_console_noise_decorator
    def setUp(self):

        self.dummy_user, _ = Contact.objects.get_or_create(
            email="mayor@igorville.com", first_name="Hello", last_name="World"
        )
        self.dummy_user_2, _ = User.objects.get_or_create(
            username="intern@igorville.com", email="intern@igorville.com", first_name="Lava", last_name="World"
        )

        self.dummy_user_3, _ = User.objects.get_or_create(
            username="portfolioadmin@igorville.com",
            email="portfolioadmin@igorville.com",
            first_name="Portfolio",
            last_name="Admin",
        )

        self.started_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
        )
        self.submitted_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            name="submitted.gov",
        )
        self.in_review_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            name="in-review.gov",
        )
        self.action_needed_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            name="action-needed.gov",
        )
        self.approved_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.APPROVED,
            name="approved.gov",
        )
        self.withdrawn_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            name="withdrawn.gov",
        )
        self.rejected_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.REJECTED,
            name="rejected.gov",
        )
        self.ineligible_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.INELIGIBLE,
            name="ineligible.gov",
        )

        # Store all domain request statuses in a variable for ease of use
        self.all_domain_requests = [
            self.started_domain_request,
            self.submitted_domain_request,
            self.in_review_domain_request,
            self.action_needed_domain_request,
            self.approved_domain_request,
            self.withdrawn_domain_request,
            self.rejected_domain_request,
            self.ineligible_domain_request,
        ]

        self.mock_client = MockSESClient()

    def tearDown(self):
        super().tearDown()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        DraftDomain.objects.all().delete()
        Domain.objects.all().delete()
        Portfolio.objects.all().delete()
        User.objects.all().delete()
        self.mock_client.EMAILS_SENT.clear()

    def assertNotRaises(self, exception_type):
        """Helper method for testing allowed transitions."""
        with less_console_noise():
            return self.assertRaises(Exception, None, exception_type)

    @less_console_noise_decorator
    def test_request_is_withdrawable(self):
        """Tests the is_withdrawable function"""
        domain_request_1 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            name="city2.gov",
        )
        domain_request_2 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            name="city3.gov",
        )
        domain_request_3 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            name="city4.gov",
        )
        domain_request_4 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.REJECTED,
            name="city5.gov",
        )
        self.assertTrue(domain_request_1.is_withdrawable())
        self.assertTrue(domain_request_2.is_withdrawable())
        self.assertTrue(domain_request_3.is_withdrawable())
        self.assertFalse(domain_request_4.is_withdrawable())

    @less_console_noise_decorator
    def test_request_is_awaiting_review(self):
        """Tests the is_awaiting_review function"""
        domain_request_1 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            name="city2.gov",
        )
        domain_request_2 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            name="city3.gov",
        )
        domain_request_3 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            name="city4.gov",
        )
        domain_request_4 = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.REJECTED,
            name="city5.gov",
        )
        self.assertTrue(domain_request_1.is_awaiting_review())
        self.assertTrue(domain_request_2.is_awaiting_review())
        self.assertFalse(domain_request_3.is_awaiting_review())
        self.assertFalse(domain_request_4.is_awaiting_review())

    @less_console_noise_decorator
    def test_federal_agency_set_to_non_federal_on_approve(self):
        """Ensures that when the federal_agency field is 'none' when .approve() is called,
        the field is set to the 'Non-Federal Agency' record"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            name="city2.gov",
            federal_agency=None,
        )

        # Ensure that the federal agency is None
        self.assertEqual(domain_request.federal_agency, None)

        # Approve the request
        domain_request.approve()
        self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.APPROVED)

        # After approval, it should be "Non-Federal agency"
        expected_federal_agency = FederalAgency.objects.filter(agency="Non-Federal Agency").first()
        self.assertEqual(domain_request.federal_agency, expected_federal_agency)

    def test_empty_create_fails(self):
        """Can't create a completely empty domain request."""
        with less_console_noise():
            with transaction.atomic():
                with self.assertRaisesRegex(IntegrityError, "requester"):
                    DomainRequest.objects.create()

    @less_console_noise_decorator
    def test_minimal_create(self):
        """Can create with just a requester."""
        user, _ = User.objects.get_or_create(username="testy")
        domain_request = DomainRequest.objects.create(requester=user)
        self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.STARTED)

    @less_console_noise_decorator
    def test_full_create(self):
        """Can create with all fields."""
        user, _ = User.objects.get_or_create(username="testy")
        contact = Contact.objects.create()
        com_website, _ = Website.objects.get_or_create(website="igorville.com")
        gov_website, _ = Website.objects.get_or_create(website="igorville.gov")
        domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            requester=user,
            investigator=user,
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            federal_type=BranchChoices.EXECUTIVE,
            is_election_board=False,
            organization_name="Test",
            address_line1="100 Main St.",
            address_line2="APT 1A",
            state_territory="CA",
            zipcode="12345-6789",
            senior_official=contact,
            requested_domain=domain,
            purpose="Igorville rules!",
            anything_else="All of Igorville loves the dotgov program.",
            is_policy_acknowledged=True,
        )
        domain_request.current_websites.add(com_website)
        domain_request.alternative_domains.add(gov_website)
        domain_request.other_contacts.add(contact)
        domain_request.save()

    @less_console_noise_decorator
    def test_domain_info(self):
        """Can create domain info with all fields."""
        user, _ = User.objects.get_or_create(username="testy")
        contact = Contact.objects.create()
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        information = DomainInformation.objects.create(
            requester=user,
            generic_org_type=DomainInformation.OrganizationChoices.FEDERAL,
            federal_type=BranchChoices.EXECUTIVE,
            is_election_board=False,
            organization_name="Test",
            address_line1="100 Main St.",
            address_line2="APT 1A",
            state_territory="CA",
            zipcode="12345-6789",
            senior_official=contact,
            purpose="Igorville rules!",
            anything_else="All of Igorville loves the dotgov program.",
            is_policy_acknowledged=True,
            domain=domain,
        )
        information.other_contacts.add(contact)
        information.save()
        self.assertEqual(information.domain.id, domain.id)
        self.assertEqual(information.id, domain.domain_info.id)

    @less_console_noise_decorator
    def test_status_fsm_submit_fail(self):
        user, _ = User.objects.get_or_create(username="testy")
        domain_request = DomainRequest.objects.create(requester=user)

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            with less_console_noise():
                with self.assertRaises(ValueError):
                    # can't submit a domain request with a null domain name
                    domain_request.submit()

    @less_console_noise_decorator
    def test_status_fsm_submit_succeed(self):
        user, _ = User.objects.get_or_create(username="testy")
        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(requester=user, requested_domain=site)

        # no email sent to requester so this emits a log warning

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            with less_console_noise():
                domain_request.submit()
        self.assertEqual(domain_request.status, domain_request.DomainRequestStatus.SUBMITTED)

    def check_email_sent(
        self,
        domain_request,
        msg,
        action,
        expected_count,
        expected_content=None,
        expected_email="mayor@igorville.com",
        expected_cc=[],
    ):
        """Check if an email was sent after performing an action."""
        email_allowed, _ = AllowedEmail.objects.get_or_create(email=expected_email)
        with self.subTest(msg=msg, action=action):
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                # Perform the specified action
                action_method = getattr(domain_request, action)
                action_method()
                domain_request.save()

            # Check if an email was sent
            sent_emails = [
                email
                for email in MockSESClient.EMAILS_SENT
                if expected_email in email["kwargs"]["Destination"]["ToAddresses"]
            ]
            self.assertEqual(len(sent_emails), expected_count)

            if expected_cc:
                sent_cc_adddresses = sent_emails[0]["kwargs"]["Destination"]["CcAddresses"]
                for cc_address in expected_cc:
                    self.assertIn(cc_address, sent_cc_adddresses)

            if expected_content:
                email_content = sent_emails[0]["kwargs"]["Content"]["Simple"]["Body"]["Text"]["Data"]
                self.assertIn(expected_content, email_content)

        email_allowed.delete()

    @less_console_noise_decorator
    def test_submit_from_started_sends_email_to_requester(self):
        """tests that we send an email to the requester"""
        msg = "Create a domain request and submit it and see if email was sent when the feature flag is on."
        domain_request = completed_domain_request(user=self.dummy_user_2)
        self.check_email_sent(
            domain_request, msg, "submit", 1, expected_content="Lava", expected_email="intern@igorville.com"
        )

    @less_console_noise_decorator
    def test_submit_from_withdrawn_sends_email(self):
        msg = "Create a withdrawn domain request and submit it and see if email was sent."
        user, _ = User.objects.get_or_create(username="testy", email="testy@town.com")
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.WITHDRAWN, user=user)
        self.check_email_sent(domain_request, msg, "submit", 1, expected_content="Hi", expected_email=user.email)

    @less_console_noise_decorator
    def test_submit_from_action_needed_does_not_send_email(self):
        msg = "Create a domain request with ACTION_NEEDED status and submit it, check if email was not sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.ACTION_NEEDED)
        self.check_email_sent(domain_request, msg, "submit", 0)

    @less_console_noise_decorator
    def test_submit_from_in_review_does_not_send_email(self):
        msg = "Create a withdrawn domain request and submit it and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        self.check_email_sent(domain_request, msg, "submit", 0)

    @less_console_noise_decorator
    def test_approve_sends_email(self):
        msg = "Create a domain request and approve it and see if email was sent."
        user, _ = User.objects.get_or_create(username="testy", email="testy@town.com")
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=user)
        self.check_email_sent(domain_request, msg, "approve", 1, expected_content="approved", expected_email=user.email)

    @less_console_noise_decorator
    def test_withdraw_sends_email(self):
        msg = "Create a domain request and withdraw it and see if email was sent."
        user, _ = User.objects.get_or_create(username="testy", email="testy@town.com")
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=user)
        self.check_email_sent(
            domain_request, msg, "withdraw", 1, expected_content="withdrawn", expected_email=user.email
        )

    def test_reject_sends_email(self):
        "Create a domain request and reject it and see if email was sent."
        user, _ = User.objects.get_or_create(username="testy", email="testy@town.com")
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED, user=user)
        expected_email = user.email
        email_allowed, _ = AllowedEmail.objects.get_or_create(email=expected_email)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            domain_request.reject()
            domain_request.rejection_reason = domain_request.RejectionReasons.CONTACTS_NOT_VERIFIED
            domain_request.rejection_reason_email = "test"
            domain_request.save()

        # Check if an email was sent
        sent_emails = [
            email
            for email in MockSESClient.EMAILS_SENT
            if expected_email in email["kwargs"]["Destination"]["ToAddresses"]
        ]
        self.assertEqual(len(sent_emails), 1)

        email_content = sent_emails[0]["kwargs"]["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("test", email_content)

        email_allowed.delete()

    @less_console_noise_decorator
    def test_reject_with_prejudice_does_not_send_email(self):
        msg = "Create a domain request and reject it with prejudice and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)
        self.check_email_sent(domain_request, msg, "reject_with_prejudice", 0)

    @less_console_noise_decorator
    def assert_fsm_transition_raises_error(self, test_cases, method_to_run):
        """Given a list of test cases, check if each transition throws the intended error"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client), less_console_noise():
            for domain_request, exception_type in test_cases:
                with self.subTest(domain_request=domain_request, exception_type=exception_type):
                    with self.assertRaises(exception_type):
                        # Retrieve the method by name from the domain_request object and call it
                        method = getattr(domain_request, method_to_run)
                        # Call the method
                        method()

    @less_console_noise_decorator
    def assert_fsm_transition_does_not_raise_error(self, test_cases, method_to_run):
        """Given a list of test cases, ensure that none of them throw transition errors"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client), less_console_noise():
            for domain_request, exception_type in test_cases:
                with self.subTest(domain_request=domain_request, exception_type=exception_type):
                    try:
                        # Retrieve the method by name from the DomainRequest object and call it
                        method = getattr(domain_request, method_to_run)
                        # Call the method
                        method()
                    except exception_type:
                        self.fail(f"{exception_type} was raised, but it was not expected.")

    @less_console_noise_decorator
    def test_submit_transition_allowed_with_no_investigator(self):
        """
        Tests for attempting to transition without an investigator.
        For submit, this should be valid in all cases.
        """

        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to none
        set_domain_request_investigators(self.all_domain_requests, None)

        self.assert_fsm_transition_does_not_raise_error(test_cases, "submit")

    @less_console_noise_decorator
    def test_submit_transition_allowed_with_investigator_not_staff(self):
        """
        Tests for attempting to transition with an investigator user that is not staff.
        For submit, this should be valid in all cases.
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to a user with no staff privs
        user, _ = User.objects.get_or_create(username="pancakesyrup", is_staff=False)
        set_domain_request_investigators(self.all_domain_requests, user)

        self.assert_fsm_transition_does_not_raise_error(test_cases, "submit")

    @less_console_noise_decorator
    def test_submit_transition_allowed(self):
        """
        Test that calling submit from allowable statuses does raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_does_not_raise_error(test_cases, "submit")

    @less_console_noise_decorator
    def test_submit_transition_allowed_twice(self):
        """
        Test that rotating between submit and in_review doesn't throw an error
        """
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            try:
                # Make a submission
                self.in_review_domain_request.submit()

                # Rerun the old method to get back to the original state
                self.in_review_domain_request.in_review()

                # Make another submission
                self.in_review_domain_request.submit()
            except TransitionNotAllowed:
                self.fail("TransitionNotAllowed was raised, but it was not expected.")

        self.assertEqual(self.in_review_domain_request.status, DomainRequest.DomainRequestStatus.SUBMITTED)

    @less_console_noise_decorator
    def test_submit_transition_not_allowed(self):
        """
        Test that calling submit against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_raises_error(test_cases, "submit")

    @less_console_noise_decorator
    def test_in_review_transition_allowed(self):
        """
        Test that calling in_review from allowable statuses does raises TransitionNotAllowed.
        """
        test_cases = [
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_does_not_raise_error(test_cases, "in_review")

    @less_console_noise_decorator
    def test_in_review_transition_not_allowed_with_no_investigator(self):
        """
        Tests for attempting to transition without an investigator
        """

        test_cases = [
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to none
        set_domain_request_investigators(self.all_domain_requests, None)

        self.assert_fsm_transition_raises_error(test_cases, "in_review")

    @less_console_noise_decorator
    def test_in_review_transition_not_allowed_with_investigator_not_staff(self):
        """
        Tests for attempting to transition with an investigator that is not staff.
        This should throw an exception.
        """

        test_cases = [
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to a user with no staff privs
        user, _ = User.objects.get_or_create(username="pancakesyrup", is_staff=False)
        set_domain_request_investigators(self.all_domain_requests, user)

        self.assert_fsm_transition_raises_error(test_cases, "in_review")

    @less_console_noise_decorator
    def test_in_review_transition_not_allowed(self):
        """
        Test that calling in_review against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_raises_error(test_cases, "in_review")

    @less_console_noise_decorator
    def test_action_needed_transition_allowed(self):
        """
        Test that calling action_needed from allowable statuses does raises TransitionNotAllowed.
        """
        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_does_not_raise_error(test_cases, "action_needed")

    @less_console_noise_decorator
    def test_action_needed_transition_not_allowed_with_no_investigator(self):
        """
        Tests for attempting to transition without an investigator
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to none
        set_domain_request_investigators(self.all_domain_requests, None)

        self.assert_fsm_transition_raises_error(test_cases, "action_needed")

    @less_console_noise_decorator
    def test_action_needed_transition_not_allowed_with_investigator_not_staff(self):
        """
        Tests for attempting to transition with an investigator that is not staff
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to a user with no staff privs
        user, _ = User.objects.get_or_create(username="pancakesyrup", is_staff=False)
        set_domain_request_investigators(self.all_domain_requests, user)

        self.assert_fsm_transition_raises_error(test_cases, "action_needed")

    @less_console_noise_decorator
    def test_action_needed_transition_not_allowed(self):
        """
        Test that calling action_needed against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_raises_error(test_cases, "action_needed")

    @less_console_noise_decorator
    def test_approved_transition_allowed(self):
        """
        Test that calling action_needed from allowable statuses does raises TransitionNotAllowed.
        """
        test_cases = [
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_does_not_raise_error(test_cases, "approve")

    @less_console_noise_decorator
    def test_approved_transition_not_allowed_with_no_investigator(self):
        """
        Tests for attempting to transition without an investigator
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to none
        set_domain_request_investigators(self.all_domain_requests, None)

        self.assert_fsm_transition_raises_error(test_cases, "approve")

    @less_console_noise_decorator
    def test_approved_transition_not_allowed_with_investigator_not_staff(self):
        """
        Tests for attempting to transition with an investigator that is not staff
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to a user with no staff privs
        user, _ = User.objects.get_or_create(username="pancakesyrup", is_staff=False)
        set_domain_request_investigators(self.all_domain_requests, user)

        self.assert_fsm_transition_raises_error(test_cases, "approve")

    @less_console_noise_decorator
    def test_approved_skips_sending_email(self):
        """
        Test that calling .approve with send_email=False doesn't actually send
        an email
        """

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            self.submitted_domain_request.approve(send_email=False)

        # Assert that no emails were sent
        self.assertEqual(len(self.mock_client.EMAILS_SENT), 0)

    @less_console_noise_decorator
    def test_approved_transition_not_allowed(self):
        """
        Test that calling approve against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]
        self.assert_fsm_transition_raises_error(test_cases, "approve")

    @less_console_noise_decorator
    def test_approved_transition_not_allowed_when_domain_already_approved(self):
        """
        Test that calling approve whith an already approved requested domain raises
        TransitionNotAllowed.
        """
        Domain.objects.all().create(name=self.submitted_domain_request.requested_domain.name)
        test_cases = [
            (self.submitted_domain_request, FSMDomainRequestError),
        ]
        self.assert_fsm_transition_raises_error(test_cases, "approve")

    @less_console_noise_decorator
    def test_withdraw_transition_allowed(self):
        """
        Test that calling action_needed from allowable statuses does raises TransitionNotAllowed.
        """
        test_cases = [
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_does_not_raise_error(test_cases, "withdraw")

    @less_console_noise_decorator
    def test_withdraw_transition_allowed_with_no_investigator(self):
        """
        Tests for attempting to transition without an investigator.
        For withdraw, this should be valid in all cases.
        """

        test_cases = [
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to none
        set_domain_request_investigators(self.all_domain_requests, None)

        self.assert_fsm_transition_does_not_raise_error(test_cases, "withdraw")

    @less_console_noise_decorator
    def test_withdraw_transition_allowed_with_investigator_not_staff(self):
        """
        Tests for attempting to transition when investigator is not staff.
        For withdraw, this should be valid in all cases.
        """

        test_cases = [
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to a user with no staff privs
        user, _ = User.objects.get_or_create(username="pancakesyrup", is_staff=False)
        set_domain_request_investigators(self.all_domain_requests, user)

        self.assert_fsm_transition_does_not_raise_error(test_cases, "withdraw")

    @less_console_noise_decorator
    def test_withdraw_transition_not_allowed(self):
        """
        Test that calling action_needed against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_raises_error(test_cases, "withdraw")

    @less_console_noise_decorator
    def test_reject_transition_allowed(self):
        """
        Test that calling action_needed from allowable statuses does raises TransitionNotAllowed.
        """
        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_does_not_raise_error(test_cases, "reject")

    @less_console_noise_decorator
    def test_reject_transition_not_allowed_with_no_investigator(self):
        """
        Tests for attempting to transition without an investigator
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to none
        set_domain_request_investigators(self.all_domain_requests, None)

        self.assert_fsm_transition_raises_error(test_cases, "reject")

    @less_console_noise_decorator
    def test_reject_transition_not_allowed_with_investigator_not_staff(self):
        """
        Tests for attempting to transition when investigator is not staff
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to a user with no staff privs
        user, _ = User.objects.get_or_create(username="pancakesyrup", is_staff=False)
        set_domain_request_investigators(self.all_domain_requests, user)

        self.assert_fsm_transition_raises_error(test_cases, "reject")

    @less_console_noise_decorator
    def test_reject_transition_not_allowed(self):
        """
        Test that calling action_needed against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_raises_error(test_cases, "reject")

    @less_console_noise_decorator
    def test_reject_with_prejudice_transition_allowed(self):
        """
        Test that calling action_needed from allowable statuses does raises TransitionNotAllowed.
        """
        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_does_not_raise_error(test_cases, "reject_with_prejudice")

    @less_console_noise_decorator
    def test_reject_with_prejudice_transition_not_allowed_with_no_investigator(self):
        """
        Tests for attempting to transition without an investigator
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to none
        set_domain_request_investigators(self.all_domain_requests, None)

        self.assert_fsm_transition_raises_error(test_cases, "reject_with_prejudice")

    @less_console_noise_decorator
    def test_reject_with_prejudice_not_allowed_with_investigator_not_staff(self):
        """
        Tests for attempting to transition when investigator is not staff
        """

        test_cases = [
            (self.in_review_domain_request, TransitionNotAllowed),
            (self.action_needed_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.rejected_domain_request, TransitionNotAllowed),
        ]

        # Set all investigators to a user with no staff privs
        user, _ = User.objects.get_or_create(username="pancakesyrup", is_staff=False)
        set_domain_request_investigators(self.all_domain_requests, user)

        self.assert_fsm_transition_raises_error(test_cases, "reject_with_prejudice")

    @less_console_noise_decorator
    def test_reject_with_prejudice_transition_not_allowed(self):
        """
        Test that calling action_needed against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.submitted_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]

        self.assert_fsm_transition_raises_error(test_cases, "reject_with_prejudice")

    @less_console_noise_decorator
    def test_transition_not_allowed_approved_in_review_when_domain_is_active(self):
        """Create a domain request with status approved, create a matching domain that
        is active, and call in_review against transition rules"""

        domain = Domain.objects.create(name=self.approved_domain_request.requested_domain.name)
        self.approved_domain_request.approved_domain = domain
        self.approved_domain_request.save()

        # Define a custom implementation for is_active
        def custom_is_active(self):
            return True  # Override to return True

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            # Use patch to temporarily replace is_active with the custom implementation
            with patch.object(Domain, "is_active", custom_is_active):
                # Now, when you call is_active on Domain, it will return True
                with self.assertRaises(TransitionNotAllowed):
                    self.approved_domain_request.in_review()

    @less_console_noise_decorator
    def test_transition_not_allowed_approved_action_needed_when_domain_is_active(self):
        """Create a domain request with status approved, create a matching domain that
        is active, and call action_needed against transition rules"""

        domain = Domain.objects.create(name=self.approved_domain_request.requested_domain.name)
        self.approved_domain_request.approved_domain = domain
        self.approved_domain_request.save()

        # Define a custom implementation for is_active
        def custom_is_active(self):
            return True  # Override to return True

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            # Use patch to temporarily replace is_active with the custom implementation
            with patch.object(Domain, "is_active", custom_is_active):
                # Now, when you call is_active on Domain, it will return True
                with self.assertRaises(TransitionNotAllowed):
                    self.approved_domain_request.action_needed()

    @less_console_noise_decorator
    def test_transition_not_allowed_approved_rejected_when_domain_is_active(self):
        """Create a domain request with status approved, create a matching domain that
        is active, and call reject against transition rules"""

        domain = Domain.objects.create(name=self.approved_domain_request.requested_domain.name)
        self.approved_domain_request.approved_domain = domain
        self.approved_domain_request.save()

        # Define a custom implementation for is_active
        def custom_is_active(self):
            return True  # Override to return True

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            # Use patch to temporarily replace is_active with the custom implementation
            with patch.object(Domain, "is_active", custom_is_active):
                # Now, when you call is_active on Domain, it will return True
                with self.assertRaises(TransitionNotAllowed):
                    self.approved_domain_request.reject()

    @less_console_noise_decorator
    def test_transition_not_allowed_approved_ineligible_when_domain_is_active(self):
        """Create a domain request with status approved, create a matching domain that
        is active, and call reject_with_prejudice against transition rules"""

        domain = Domain.objects.create(name=self.approved_domain_request.requested_domain.name)
        self.approved_domain_request.approved_domain = domain
        self.approved_domain_request.save()

        # Define a custom implementation for is_active
        def custom_is_active(self):
            return True  # Override to return True

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            # Use patch to temporarily replace is_active with the custom implementation
            with patch.object(Domain, "is_active", custom_is_active):
                # Now, when you call is_active on Domain, it will return True
                with self.assertRaises(TransitionNotAllowed):
                    self.approved_domain_request.reject_with_prejudice()

    @less_console_noise_decorator
    def test_approve_from_rejected_clears_rejection_reason(self):
        """When transitioning from rejected to approved on a domain request,
        the rejection_reason is cleared."""

        # Create a sample domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.REJECTED)
        domain_request.rejection_reason = DomainRequest.RejectionReasons.DOMAIN_PURPOSE

        # Approve
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            domain_request.approve()

        self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.APPROVED)
        self.assertEqual(domain_request.rejection_reason, None)

    @less_console_noise_decorator
    def test_in_review_from_rejected_clears_rejection_reason(self):
        """When transitioning from rejected to in_review on a domain request,
        the rejection_reason is cleared."""

        # Create a sample domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.REJECTED)
        domain_request.domain_is_not_active = True
        domain_request.rejection_reason = DomainRequest.RejectionReasons.DOMAIN_PURPOSE

        # Approve
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            domain_request.in_review()

        self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.IN_REVIEW)
        self.assertEqual(domain_request.rejection_reason, None)

    @less_console_noise_decorator
    def test_action_needed_from_rejected_clears_rejection_reason(self):
        """When transitioning from rejected to action_needed on a domain request,
        the rejection_reason is cleared."""

        # Create a sample domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.REJECTED)
        domain_request.domain_is_not_active = True
        domain_request.rejection_reason = DomainRequest.RejectionReasons.DOMAIN_PURPOSE

        # Approve
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            domain_request.action_needed()

        self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.ACTION_NEEDED)
        self.assertEqual(domain_request.rejection_reason, None)

    @less_console_noise_decorator
    def test_has_rationale_returns_true(self):
        """has_rationale() returns true when a domain request has no_other_contacts_rationale"""
        self.started_domain_request.no_other_contacts_rationale = "You talkin' to me?"
        self.started_domain_request.save()
        self.assertEquals(self.started_domain_request.has_rationale(), True)

    @less_console_noise_decorator
    def test_has_rationale_returns_false(self):
        """has_rationale() returns false when a domain request has no no_other_contacts_rationale"""
        self.assertEquals(self.started_domain_request.has_rationale(), False)

    @less_console_noise_decorator
    def test_has_other_contacts_returns_true(self):
        """has_other_contacts() returns true when a domain request has other_contacts"""
        # completed_domain_request has other contacts by default
        self.assertEquals(self.started_domain_request.has_other_contacts(), True)

    @less_console_noise_decorator
    def test_has_other_contacts_returns_false(self):
        """has_other_contacts() returns false when a domain request has no other_contacts"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED, name="no-others.gov", has_other_contacts=False
        )
        self.assertEquals(domain_request.has_other_contacts(), False)

    @less_console_noise_decorator
    def test_converted_type(self):
        """test that new property fields works as expected to pull domain req info such as fed agency,
        generic org type, and others from portfolio"""
        fed_agency = FederalAgency.objects.filter(agency="Non-Federal Agency").first()
        portfolio = Portfolio.objects.create(
            organization_name="Test Portfolio",
            requester=self.dummy_user_2,
            federal_agency=fed_agency,
            organization_type=DomainRequest.OrganizationChoices.FEDERAL,
        )

        domain_request = completed_domain_request(name="domainre1.gov", portfolio=portfolio)

        self.assertEqual(portfolio.organization_type, domain_request.converted_generic_org_type)
        self.assertEqual(portfolio.federal_agency, domain_request.converted_federal_agency)

        domain_request2 = completed_domain_request(
            name="domainreq2.gov", federal_agency=fed_agency, generic_org_type=DomainRequest.OrganizationChoices.TRIBAL
        )
        self.assertEqual(domain_request2.generic_org_type, domain_request2.converted_generic_org_type)
        self.assertEqual(domain_request2.federal_agency, domain_request2.converted_federal_agency)

    @less_console_noise_decorator
    def test_portfolio_domain_requests_cc_requests_viewers(self):
        """test that portfolio domain request emails cc portfolio members who have read requests access"""
        fed_agency = FederalAgency.objects.filter(agency="Non-Federal Agency").first()
        portfolio = Portfolio.objects.create(
            organization_name="Test Portfolio",
            requester=self.dummy_user_2,
            federal_agency=fed_agency,
            organization_type=DomainRequest.OrganizationChoices.FEDERAL,
        )
        UserPortfolioPermission.objects.create(
            user=self.dummy_user_3, portfolio=portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        # Adds cc'ed email in this test's allow list
        AllowedEmail.objects.create(email="portfolioadmin@igorville.com")

        msg = "Create a domain request and submit it and see if email cc's portfolio admin and members who can view \
            requests."
        domain_request = completed_domain_request(
            name="test.gov", user=self.dummy_user_2, portfolio=portfolio, organization_name="Test Portfolio"
        )
        self.check_email_sent(
            domain_request,
            msg,
            "submit",
            1,
            expected_email="intern@igorville.com",
            expected_cc=["portfolioadmin@igorville.com"],
        )


class TestDomainRequestSuborganization(TestCase):
    """Tests for the suborganization fields on domain requests"""

    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.superuser = create_superuser()

    def tearDown(self):
        super().tearDown()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Domain.objects.all().delete()
        Suborganization.objects.all().delete()
        Portfolio.objects.all().delete()

    @less_console_noise_decorator
    def test_approve_creates_requested_suborganization(self):
        """Test that approving a domain request with a requested suborganization creates it"""
        portfolio = Portfolio.objects.create(organization_name="Test Org", requester=self.user)

        domain_request = completed_domain_request(
            name="test.gov",
            portfolio=portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            requested_suborganization="Boom",
            suborganization_city="Explody town",
            suborganization_state_territory=DomainRequest.StateTerritoryChoices.OHIO,
        )
        domain_request.investigator = self.superuser
        domain_request.save()

        domain_request.approve()

        created_suborg = Suborganization.objects.filter(
            name="Boom",
            city="Explody town",
            state_territory=DomainRequest.StateTerritoryChoices.OHIO,
            portfolio=portfolio,
        ).first()

        self.assertIsNotNone(created_suborg)
        self.assertEqual(domain_request.sub_organization, created_suborg)

    @less_console_noise_decorator
    def test_approve_without_requested_suborganization_makes_no_changes(self):
        """Test that approving without a requested suborganization doesn't create one"""
        portfolio = Portfolio.objects.create(organization_name="Test Org", requester=self.user)

        domain_request = completed_domain_request(
            name="test.gov",
            portfolio=portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        domain_request.investigator = self.superuser
        domain_request.save()

        initial_suborg_count = Suborganization.objects.count()
        domain_request.approve()

        self.assertEqual(Suborganization.objects.count(), initial_suborg_count)
        self.assertIsNone(domain_request.sub_organization)

    @less_console_noise_decorator
    def test_approve_with_existing_suborganization_makes_no_changes(self):
        """Test that approving with an existing suborganization doesn't create a new one"""
        portfolio = Portfolio.objects.create(organization_name="Test Org", requester=self.user)
        existing_suborg = Suborganization.objects.create(name="Existing Division", portfolio=portfolio)

        domain_request = completed_domain_request(
            name="test.gov",
            portfolio=portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            sub_organization=existing_suborg,
        )
        domain_request.investigator = self.superuser
        domain_request.save()

        initial_suborg_count = Suborganization.objects.count()
        domain_request.approve()

        self.assertEqual(Suborganization.objects.count(), initial_suborg_count)
        self.assertEqual(domain_request.sub_organization, existing_suborg)

    @less_console_noise_decorator
    def test_cleanup_dangling_suborg_with_single_reference(self):
        """Test that a suborganization is deleted when it's only referenced once"""
        portfolio = Portfolio.objects.create(organization_name="Test Org", requester=self.user)
        suborg = Suborganization.objects.create(name="Test Division", portfolio=portfolio)

        domain_request = completed_domain_request(
            name="test.gov",
            portfolio=portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            sub_organization=suborg,
        )
        domain_request.approve()

        # set it back to in review
        domain_request.in_review()
        domain_request.refresh_from_db()

        # Verify the suborganization was deleted
        self.assertFalse(Suborganization.objects.filter(id=suborg.id).exists())
        self.assertIsNone(domain_request.sub_organization)

    @less_console_noise_decorator
    def test_cleanup_dangling_suborg_with_multiple_references(self):
        """Test that a suborganization is preserved when it has multiple references"""
        portfolio = Portfolio.objects.create(organization_name="Test Org", requester=self.user)
        suborg = Suborganization.objects.create(name="Test Division", portfolio=portfolio)

        # Create two domain requests using the same suborganization
        domain_request1 = completed_domain_request(
            name="test1.gov",
            portfolio=portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            sub_organization=suborg,
        )
        domain_request2 = completed_domain_request(
            name="test2.gov",
            portfolio=portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            sub_organization=suborg,
        )

        domain_request1.approve()
        domain_request2.approve()

        # set one back to in review
        domain_request1.in_review()
        domain_request1.refresh_from_db()

        # Verify the suborganization still exists
        self.assertTrue(Suborganization.objects.filter(id=suborg.id).exists())
        self.assertEqual(domain_request1.sub_organization, suborg)
        self.assertEqual(domain_request2.sub_organization, suborg)
