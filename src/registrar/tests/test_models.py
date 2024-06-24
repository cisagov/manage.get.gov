from django.test import TestCase
from django.db.utils import IntegrityError
from unittest.mock import patch
from django.contrib.auth import get_user_model

from django.test import RequestFactory

from registrar.models import (
    Contact,
    DomainRequest,
    DomainInformation,
    User,
    Website,
    Domain,
    DraftDomain,
    DomainInvitation,
    UserDomainRole,
    FederalAgency,
)

import boto3_mocking
from registrar.models.transition_domain import TransitionDomain
from registrar.models.verified_by_staff import VerifiedByStaff  # type: ignore
from registrar.utility.constants import BranchChoices

from .common import MockSESClient, less_console_noise, completed_domain_request, set_domain_request_investigators
from django_fsm import TransitionNotAllowed


# Test comment for push -- will remove
# The DomainRequest submit method has a side effect of sending an email
# with AWS SES, so mock that out in all of these test cases
@boto3_mocking.patching
class TestDomainRequest(TestCase):
    def setUp(self):
        self.started_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED, name="started.gov"
        )
        self.submitted_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.SUBMITTED, name="submitted.gov"
        )
        self.in_review_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, name="in-review.gov"
        )
        self.action_needed_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.ACTION_NEEDED, name="action-needed.gov"
        )
        self.approved_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.APPROVED, name="approved.gov"
        )
        self.withdrawn_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.WITHDRAWN, name="withdrawn.gov"
        )
        self.rejected_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.REJECTED, name="rejected.gov"
        )
        self.ineligible_domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.INELIGIBLE, name="ineligible.gov"
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
        self.mock_client.EMAILS_SENT.clear()

    def assertNotRaises(self, exception_type):
        """Helper method for testing allowed transitions."""
        with less_console_noise():
            return self.assertRaises(Exception, None, exception_type)

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
        """Can't create a completely empty domain request.
        NOTE: something about theexception this test raises messes up with the
        atomic block in a custom tearDown method for the parent test class."""
        with less_console_noise():
            with self.assertRaisesRegex(IntegrityError, "creator"):
                DomainRequest.objects.create()

    def test_minimal_create(self):
        """Can create with just a creator."""
        with less_console_noise():
            user, _ = User.objects.get_or_create(username="testy")
            domain_request = DomainRequest.objects.create(creator=user)
            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.STARTED)

    def test_full_create(self):
        """Can create with all fields."""
        with less_console_noise():
            user, _ = User.objects.get_or_create(username="testy")
            contact = Contact.objects.create()
            com_website, _ = Website.objects.get_or_create(website="igorville.com")
            gov_website, _ = Website.objects.get_or_create(website="igorville.gov")
            domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
            domain_request = DomainRequest.objects.create(
                creator=user,
                investigator=user,
                generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
                federal_type=BranchChoices.EXECUTIVE,
                is_election_board=False,
                organization_name="Test",
                address_line1="100 Main St.",
                address_line2="APT 1A",
                state_territory="CA",
                zipcode="12345-6789",
                authorizing_official=contact,
                requested_domain=domain,
                submitter=contact,
                purpose="Igorville rules!",
                anything_else="All of Igorville loves the dotgov program.",
                is_policy_acknowledged=True,
            )
            domain_request.current_websites.add(com_website)
            domain_request.alternative_domains.add(gov_website)
            domain_request.other_contacts.add(contact)
            domain_request.save()

    def test_domain_info(self):
        """Can create domain info with all fields."""
        with less_console_noise():
            user, _ = User.objects.get_or_create(username="testy")
            contact = Contact.objects.create()
            domain, _ = Domain.objects.get_or_create(name="igorville.gov")
            information = DomainInformation.objects.create(
                creator=user,
                generic_org_type=DomainInformation.OrganizationChoices.FEDERAL,
                federal_type=BranchChoices.EXECUTIVE,
                is_election_board=False,
                organization_name="Test",
                address_line1="100 Main St.",
                address_line2="APT 1A",
                state_territory="CA",
                zipcode="12345-6789",
                authorizing_official=contact,
                submitter=contact,
                purpose="Igorville rules!",
                anything_else="All of Igorville loves the dotgov program.",
                is_policy_acknowledged=True,
                domain=domain,
            )
            information.other_contacts.add(contact)
            information.save()
            self.assertEqual(information.domain.id, domain.id)
            self.assertEqual(information.id, domain.domain_info.id)

    def test_status_fsm_submit_fail(self):
        with less_console_noise():
            user, _ = User.objects.get_or_create(username="testy")
            domain_request = DomainRequest.objects.create(creator=user)

            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                with less_console_noise():
                    with self.assertRaises(ValueError):
                        # can't submit a domain request with a null domain name
                        domain_request.submit()

    def test_status_fsm_submit_succeed(self):
        with less_console_noise():
            user, _ = User.objects.get_or_create(username="testy")
            site = DraftDomain.objects.create(name="igorville.gov")
            domain_request = DomainRequest.objects.create(creator=user, requested_domain=site)

            # no submitter email so this emits a log warning

            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                with less_console_noise():
                    domain_request.submit()
            self.assertEqual(domain_request.status, domain_request.DomainRequestStatus.SUBMITTED)

    def check_email_sent(self, domain_request, msg, action, expected_count):
        """Check if an email was sent after performing an action."""

        with self.subTest(msg=msg, action=action):
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                with less_console_noise():
                    # Perform the specified action
                    action_method = getattr(domain_request, action)
                    action_method()

            # Check if an email was sent
            sent_emails = [
                email
                for email in MockSESClient.EMAILS_SENT
                if "mayor@igorville.gov" in email["kwargs"]["Destination"]["ToAddresses"]
            ]
            self.assertEqual(len(sent_emails), expected_count)

    def test_submit_from_started_sends_email(self):
        msg = "Create a domain request and submit it and see if email was sent."
        domain_request = completed_domain_request()
        self.check_email_sent(domain_request, msg, "submit", 1)

    def test_submit_from_withdrawn_sends_email(self):
        msg = "Create a withdrawn domain request and submit it and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.WITHDRAWN)
        self.check_email_sent(domain_request, msg, "submit", 1)

    def test_submit_from_action_needed_does_not_send_email(self):
        msg = "Create a domain request with ACTION_NEEDED status and submit it, check if email was not sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.ACTION_NEEDED)
        self.check_email_sent(domain_request, msg, "submit", 0)

    def test_submit_from_in_review_does_not_send_email(self):
        msg = "Create a withdrawn domain request and submit it and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        self.check_email_sent(domain_request, msg, "submit", 0)

    def test_approve_sends_email(self):
        msg = "Create a domain request and approve it and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        self.check_email_sent(domain_request, msg, "approve", 1)

    def test_withdraw_sends_email(self):
        msg = "Create a domain request and withdraw it and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        self.check_email_sent(domain_request, msg, "withdraw", 1)

    def test_reject_sends_email(self):
        msg = "Create a domain request and reject it and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)
        self.check_email_sent(domain_request, msg, "reject", 1)

    def test_reject_with_prejudice_does_not_send_email(self):
        msg = "Create a domain request and reject it with prejudice and see if email was sent."
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)
        self.check_email_sent(domain_request, msg, "reject_with_prejudice", 0)

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

    def test_submit_transition_allowed_twice(self):
        """
        Test that rotating between submit and in_review doesn't throw an error
        """
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            with less_console_noise():
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

    def test_approved_skips_sending_email(self):
        """
        Test that calling .approve with send_email=False doesn't actually send
        an email
        """

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            with less_console_noise():
                self.submitted_domain_request.approve(send_email=False)

        # Assert that no emails were sent
        self.assertEqual(len(self.mock_client.EMAILS_SENT), 0)

    def test_approved_transition_not_allowed(self):
        """
        Test that calling action_needed against transition rules raises TransitionNotAllowed.
        """
        test_cases = [
            (self.started_domain_request, TransitionNotAllowed),
            (self.approved_domain_request, TransitionNotAllowed),
            (self.withdrawn_domain_request, TransitionNotAllowed),
            (self.ineligible_domain_request, TransitionNotAllowed),
        ]
        self.assert_fsm_transition_raises_error(test_cases, "approve")

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
            with less_console_noise():
                # Use patch to temporarily replace is_active with the custom implementation
                with patch.object(Domain, "is_active", custom_is_active):
                    # Now, when you call is_active on Domain, it will return True
                    with self.assertRaises(TransitionNotAllowed):
                        self.approved_domain_request.in_review()

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
            with less_console_noise():
                # Use patch to temporarily replace is_active with the custom implementation
                with patch.object(Domain, "is_active", custom_is_active):
                    # Now, when you call is_active on Domain, it will return True
                    with self.assertRaises(TransitionNotAllowed):
                        self.approved_domain_request.action_needed()

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
            with less_console_noise():
                # Use patch to temporarily replace is_active with the custom implementation
                with patch.object(Domain, "is_active", custom_is_active):
                    # Now, when you call is_active on Domain, it will return True
                    with self.assertRaises(TransitionNotAllowed):
                        self.approved_domain_request.reject()

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
            with less_console_noise():
                # Use patch to temporarily replace is_active with the custom implementation
                with patch.object(Domain, "is_active", custom_is_active):
                    # Now, when you call is_active on Domain, it will return True
                    with self.assertRaises(TransitionNotAllowed):
                        self.approved_domain_request.reject_with_prejudice()

    def test_approve_from_rejected_clears_rejection_reason(self):
        """When transitioning from rejected to approved on a domain request,
        the rejection_reason is cleared."""

        with less_console_noise():
            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.REJECTED)
            domain_request.rejection_reason = DomainRequest.RejectionReasons.DOMAIN_PURPOSE

            # Approve
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.approve()

            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.APPROVED)
            self.assertEqual(domain_request.rejection_reason, None)

    def test_in_review_from_rejected_clears_rejection_reason(self):
        """When transitioning from rejected to in_review on a domain request,
        the rejection_reason is cleared."""

        with less_console_noise():
            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.REJECTED)
            domain_request.domain_is_not_active = True
            domain_request.rejection_reason = DomainRequest.RejectionReasons.DOMAIN_PURPOSE

            # Approve
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.in_review()

            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.IN_REVIEW)
            self.assertEqual(domain_request.rejection_reason, None)

    def test_action_needed_from_rejected_clears_rejection_reason(self):
        """When transitioning from rejected to action_needed on a domain request,
        the rejection_reason is cleared."""

        with less_console_noise():
            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.REJECTED)
            domain_request.domain_is_not_active = True
            domain_request.rejection_reason = DomainRequest.RejectionReasons.DOMAIN_PURPOSE

            # Approve
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.action_needed()

            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.ACTION_NEEDED)
            self.assertEqual(domain_request.rejection_reason, None)

    def test_has_rationale_returns_true(self):
        """has_rationale() returns true when a domain request has no_other_contacts_rationale"""
        with less_console_noise():
            self.started_domain_request.no_other_contacts_rationale = "You talkin' to me?"
            self.started_domain_request.save()
            self.assertEquals(self.started_domain_request.has_rationale(), True)

    def test_has_rationale_returns_false(self):
        """has_rationale() returns false when a domain request has no no_other_contacts_rationale"""
        with less_console_noise():
            self.assertEquals(self.started_domain_request.has_rationale(), False)

    def test_has_other_contacts_returns_true(self):
        """has_other_contacts() returns true when a domain request has other_contacts"""
        with less_console_noise():
            # completed_domain_request has other contacts by default
            self.assertEquals(self.started_domain_request.has_other_contacts(), True)

    def test_has_other_contacts_returns_false(self):
        """has_other_contacts() returns false when a domain request has no other_contacts"""
        with less_console_noise():
            domain_request = completed_domain_request(
                status=DomainRequest.DomainRequestStatus.STARTED, name="no-others.gov", has_other_contacts=False
            )
            self.assertEquals(domain_request.has_other_contacts(), False)


class TestPermissions(TestCase):
    """Test the User-Domain-Role connection."""

    def setUp(self):
        super().setUp()
        self.mock_client = MockSESClient()

    def tearDown(self):
        super().tearDown()
        self.mock_client.EMAILS_SENT.clear()

    @boto3_mocking.patching
    def test_approval_creates_role(self):
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        investigator, _ = User.objects.get_or_create(username="frenchtoast", is_staff=True)
        domain_request = DomainRequest.objects.create(
            creator=user, requested_domain=draft_domain, investigator=investigator
        )

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            with less_console_noise():
                # skip using the submit method
                domain_request.status = DomainRequest.DomainRequestStatus.SUBMITTED
                domain_request.approve()

        # should be a role for this user
        domain = Domain.objects.get(name="igorville.gov")
        self.assertTrue(UserDomainRole.objects.get(user=user, domain=domain))


class TestDomainInformation(TestCase):
    """Test the DomainInformation model, when approved or otherwise"""

    def setUp(self):
        super().setUp()
        self.mock_client = MockSESClient()

    def tearDown(self):
        super().tearDown()
        self.mock_client.EMAILS_SENT.clear()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        DraftDomain.objects.all().delete()

    @boto3_mocking.patching
    def test_approval_creates_info(self):
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        investigator, _ = User.objects.get_or_create(username="frenchtoast", is_staff=True)
        domain_request = DomainRequest.objects.create(
            creator=user, requested_domain=draft_domain, notes="test notes", investigator=investigator
        )

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            with less_console_noise():
                # skip using the submit method
                domain_request.status = DomainRequest.DomainRequestStatus.SUBMITTED
                domain_request.approve()

        # should be an information present for this domain
        domain = Domain.objects.get(name="igorville.gov")
        domain_information = DomainInformation.objects.filter(domain=domain)
        self.assertTrue(domain_information.exists())

        # Test that both objects are what we expect
        current_domain_information = domain_information.get().__dict__
        expected_domain_information = DomainInformation(
            creator=user,
            domain=domain,
            notes="test notes",
            domain_request=domain_request,
            federal_agency=FederalAgency.objects.get(agency="Non-Federal Agency"),
        ).__dict__

        # Test the two records for consistency
        self.assertEqual(self.clean_dict(current_domain_information), self.clean_dict(expected_domain_information))

    def clean_dict(self, dict_obj):
        """Cleans dynamic fields in a dictionary"""
        bad_fields = ["_state", "created_at", "id", "updated_at"]
        return {k: v for k, v in dict_obj.items() if k not in bad_fields}


class TestInvitations(TestCase):
    """Test the retrieval of invitations."""

    def setUp(self):
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.email = "mayor@igorville.gov"
        self.invitation, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=self.domain)
        self.user, _ = User.objects.get_or_create(email=self.email)

        # clean out the roles each time
        UserDomainRole.objects.all().delete()

    def test_retrieval_creates_role(self):
        self.invitation.retrieve()
        self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))

    def test_retrieve_missing_user_error(self):
        # get rid of matching users
        User.objects.filter(email=self.email).delete()
        with self.assertRaises(RuntimeError):
            self.invitation.retrieve()

    def test_retrieve_existing_role_no_error(self):
        # make the overlapping role
        UserDomainRole.objects.get_or_create(user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        # this is not an error but does produce a console warning
        with less_console_noise():
            self.invitation.retrieve()
        self.assertEqual(self.invitation.status, DomainInvitation.DomainInvitationStatus.RETRIEVED)

    def test_retrieve_on_each_login(self):
        """A user's authenticate on_each_login callback retrieves their invitations."""
        self.user.on_each_login()
        self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))


class TestUser(TestCase):
    """Test actions that occur on user login,
    test class method that controls how users get validated."""

    def setUp(self):
        self.email = "mayor@igorville.gov"
        self.domain_name = "igorvilleInTransition.gov"
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.user, _ = User.objects.get_or_create(email=self.email)

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInvitation.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        DraftDomain.objects.all().delete()
        TransitionDomain.objects.all().delete()
        User.objects.all().delete()
        UserDomainRole.objects.all().delete()

    def test_check_transition_domains_without_domains_on_login(self):
        """A user's on_each_login callback does not check transition domains.
        This test makes sure that in the event a domain does not exist
        for a given transition domain, both a domain and domain invitation
        are created."""
        self.user.on_each_login()
        self.assertFalse(Domain.objects.filter(name=self.domain_name).exists())

    def test_identity_verification_with_domain_manager(self):
        """A domain manager should return False when tested with class
        method needs_identity_verification"""
        UserDomainRole.objects.get_or_create(user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    def test_identity_verification_with_transition_user(self):
        """A user from the Verisign transition should return False
        when tested with class method needs_identity_verification"""
        TransitionDomain.objects.get_or_create(username=self.user.email, domain_name=self.domain_name)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    def test_identity_verification_with_very_important_person(self):
        """A Very Important Person should return False
        when tested with class method needs_identity_verification"""
        VerifiedByStaff.objects.get_or_create(email=self.user.email)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    def test_identity_verification_with_invited_user(self):
        """An invited user should return False when tested with class
        method needs_identity_verification"""
        DomainInvitation.objects.get_or_create(email=self.user.email, domain=self.domain)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    def test_identity_verification_with_new_user(self):
        """A new user who's neither transitioned nor invited should
        return True when tested with class method needs_identity_verification"""
        self.assertTrue(User.needs_identity_verification(self.user.email, self.user.username))

    def test_check_domain_invitations_on_login_caps_email(self):
        """A DomainInvitation with an email address with capital letters should match
        a User record whose email address is not in caps"""
        # create DomainInvitation with CAPS email that matches User email
        # on a case-insensitive match
        caps_email = "MAYOR@igorville.gov"
        # mock the domain invitation save routine
        with patch("registrar.models.DomainInvitation.save") as save_mock:
            with less_console_noise():
                DomainInvitation.objects.get_or_create(email=caps_email, domain=self.domain)
                self.user.check_domain_invitations_on_login()
                # if check_domain_invitations_on_login properly matches exactly one
                # Domain Invitation, then save routine should be called exactly once
                save_mock.assert_called_once()

    def test_approved_domains_count(self):
        """Test that the correct approved domain count is returned for a user"""
        # with no associated approved domains, expect this to return 0
        self.assertEquals(self.user.get_approved_domains_count(), 0)
        # with one approved domain, expect this to return 1
        UserDomainRole.objects.get_or_create(user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 1)
        # with one approved domain, expect this to return 1 (domain2 is deleted, so not considered approved)
        domain2, _ = Domain.objects.get_or_create(name="igorville2.gov", state=Domain.State.DELETED)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain2, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 1)
        # with two approved domains, expect this to return 2
        domain3, _ = Domain.objects.get_or_create(name="igorville3.gov", state=Domain.State.DNS_NEEDED)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain3, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 2)
        # with three approved domains, expect this to return 3
        domain4, _ = Domain.objects.get_or_create(name="igorville4.gov", state=Domain.State.ON_HOLD)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain4, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 3)
        # with four approved domains, expect this to return 4
        domain5, _ = Domain.objects.get_or_create(name="igorville5.gov", state=Domain.State.READY)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain5, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 4)

    def test_active_requests_count(self):
        """Test that the correct active domain requests count is returned for a user"""
        # with no associated active requests, expect this to return 0
        self.assertEquals(self.user.get_active_requests_count(), 0)
        # with one active request, expect this to return 1
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville1.gov")
        DomainRequest.objects.create(
            creator=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.SUBMITTED
        )
        self.assertEquals(self.user.get_active_requests_count(), 1)
        # with two active requests, expect this to return 2
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville2.gov")
        DomainRequest.objects.create(
            creator=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.IN_REVIEW
        )
        self.assertEquals(self.user.get_active_requests_count(), 2)
        # with three active requests, expect this to return 3
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville3.gov")
        DomainRequest.objects.create(
            creator=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.ACTION_NEEDED
        )
        self.assertEquals(self.user.get_active_requests_count(), 3)
        # with three active requests, expect this to return 3 (STARTED is not considered active)
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville4.gov")
        DomainRequest.objects.create(
            creator=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.STARTED
        )
        self.assertEquals(self.user.get_active_requests_count(), 3)

    def test_rejected_requests_count(self):
        """Test that the correct rejected domain requests count is returned for a user"""
        # with no associated rejected requests, expect this to return 0
        self.assertEquals(self.user.get_rejected_requests_count(), 0)
        # with one rejected request, expect this to return 1
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville1.gov")
        DomainRequest.objects.create(
            creator=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.REJECTED
        )
        self.assertEquals(self.user.get_rejected_requests_count(), 1)

    def test_ineligible_requests_count(self):
        """Test that the correct ineligible domain requests count is returned for a user"""
        # with no associated ineligible requests, expect this to return 0
        self.assertEquals(self.user.get_ineligible_requests_count(), 0)
        # with one ineligible request, expect this to return 1
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville1.gov")
        DomainRequest.objects.create(
            creator=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.INELIGIBLE
        )
        self.assertEquals(self.user.get_ineligible_requests_count(), 1)

    def test_has_contact_info(self):
        """Test that has_contact_info properly returns"""
        # test with a user with contact info defined
        self.assertTrue(self.user.has_contact_info())
        # test with a user without contact info defined
        self.user.contact.title = None
        self.user.contact.email = None
        self.user.contact.phone = None
        self.assertFalse(self.user.has_contact_info())


class TestContact(TestCase):
    def setUp(self):
        self.email_for_invalid = "intern@igorville.gov"
        self.invalid_user, _ = User.objects.get_or_create(
            username=self.email_for_invalid,
            email=self.email_for_invalid,
            first_name="",
            last_name="",
            phone="",
        )
        self.invalid_contact, _ = Contact.objects.get_or_create(user=self.invalid_user)

        self.email = "mayor@igorville.gov"
        self.user, _ = User.objects.get_or_create(
            email=self.email, first_name="Jeff", last_name="Lebowski", phone="123456789"
        )
        self.contact, _ = Contact.objects.get_or_create(user=self.user)

        self.contact_as_ao, _ = Contact.objects.get_or_create(email="newguy@igorville.gov")
        self.domain_request = DomainRequest.objects.create(creator=self.user, authorizing_official=self.contact_as_ao)

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()
        User.objects.all().delete()

    def test_saving_contact_updates_user_first_last_names_and_phone(self):
        """When a contact is updated, we propagate the changes to the linked user if it exists."""

        # User and Contact are created and linked as expected.
        # An empty User object should create an empty contact.
        self.assertEqual(self.invalid_contact.first_name, "")
        self.assertEqual(self.invalid_contact.last_name, "")
        self.assertEqual(self.invalid_contact.phone, "")
        self.assertEqual(self.invalid_user.first_name, "")
        self.assertEqual(self.invalid_user.last_name, "")
        self.assertEqual(self.invalid_user.phone, "")

        # Manually update the contact - mimicking production (pre-existing data)
        self.invalid_contact.first_name = "Joey"
        self.invalid_contact.last_name = "Baloney"
        self.invalid_contact.phone = "123456789"
        self.invalid_contact.save()

        # Refresh the user object to reflect the changes made in the database
        self.invalid_user.refresh_from_db()

        # Updating the contact's first and last names propagate to the user
        self.assertEqual(self.invalid_contact.first_name, "Joey")
        self.assertEqual(self.invalid_contact.last_name, "Baloney")
        self.assertEqual(self.invalid_contact.phone, "123456789")
        self.assertEqual(self.invalid_user.first_name, "Joey")
        self.assertEqual(self.invalid_user.last_name, "Baloney")
        self.assertEqual(self.invalid_user.phone, "123456789")

    def test_saving_contact_does_not_update_user_first_last_names_and_phone(self):
        """When a contact is updated, we avoid propagating the changes to the linked user if it already has a value"""

        # User and Contact are created and linked as expected
        self.assertEqual(self.contact.first_name, "Jeff")
        self.assertEqual(self.contact.last_name, "Lebowski")
        self.assertEqual(self.contact.phone, "123456789")
        self.assertEqual(self.user.first_name, "Jeff")
        self.assertEqual(self.user.last_name, "Lebowski")
        self.assertEqual(self.user.phone, "123456789")

        self.contact.first_name = "Joey"
        self.contact.last_name = "Baloney"
        self.contact.phone = "987654321"
        self.contact.save()

        # Refresh the user object to reflect the changes made in the database
        self.user.refresh_from_db()

        # Updating the contact's first and last names propagate to the user
        self.assertEqual(self.contact.first_name, "Joey")
        self.assertEqual(self.contact.last_name, "Baloney")
        self.assertEqual(self.contact.phone, "987654321")
        self.assertEqual(self.user.first_name, "Jeff")
        self.assertEqual(self.user.last_name, "Lebowski")
        self.assertEqual(self.user.phone, "123456789")

    def test_saving_contact_does_not_update_user_email(self):
        """When a contact's email is updated, the change is not propagated to the user."""
        self.contact.email = "joey.baloney@diaperville.com"
        self.contact.save()

        # Refresh the user object to reflect the changes made in the database
        self.user.refresh_from_db()

        # Updating the contact's email does not propagate
        self.assertEqual(self.contact.email, "joey.baloney@diaperville.com")
        self.assertEqual(self.user.email, "mayor@igorville.gov")

    def test_saving_contact_does_not_update_user_email_when_none(self):
        """When a contact's email is updated, and the first/last name is none,
        the change is not propagated to the user."""
        self.invalid_contact.email = "joey.baloney@diaperville.com"
        self.invalid_contact.save()

        # Refresh the user object to reflect the changes made in the database
        self.invalid_user.refresh_from_db()

        # Updating the contact's email does not propagate
        self.assertEqual(self.invalid_contact.email, "joey.baloney@diaperville.com")
        self.assertEqual(self.invalid_user.email, "intern@igorville.gov")

    def test_has_more_than_one_join(self):
        """Test the Contact model method, has_more_than_one_join"""
        # test for a contact which has one user defined
        self.assertFalse(self.contact.has_more_than_one_join("user"))
        self.assertTrue(self.contact.has_more_than_one_join("authorizing_official"))
        # test for a contact which is assigned as an authorizing official on a domain request
        self.assertFalse(self.contact_as_ao.has_more_than_one_join("authorizing_official"))
        self.assertTrue(self.contact_as_ao.has_more_than_one_join("submitted_domain_requests"))

    def test_has_contact_info(self):
        """Test that has_contact_info properly returns"""
        # test with a contact with contact info defined
        self.assertTrue(self.contact.has_contact_info())
        # test with a contact without contact info defined
        self.contact.title = None
        self.contact.email = None
        self.contact.phone = None
        self.assertFalse(self.contact.has_contact_info())


class TestDomainRequestCustomSave(TestCase):
    """Tests custom save behaviour on the DomainRequest object"""

    def tearDown(self):
        DomainRequest.objects.all().delete()
        super().tearDown()

    def test_create_or_update_organization_type_new_instance(self):
        """Test create_or_update_organization_type when creating a new instance"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

    def test_create_or_update_organization_type_new_instance_federal_does_nothing(self):
        """Test if create_or_update_organization_type does nothing when creating a new instance for federal"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            is_election_board=True,
        )
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.FEDERAL)
        self.assertEqual(domain_request.is_election_board, None)

    def test_create_or_update_organization_type_existing_instance_updates_election_board(self):
        """Test create_or_update_organization_type for an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_request.is_election_board = True
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, True)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

        # Try reverting the election board value
        domain_request.is_election_board = False
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

        # Try reverting setting an invalid value for election board (should revert to False)
        domain_request.is_election_board = None
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

    def test_create_or_update_organization_type_existing_instance_updates_generic_org_type(self):
        """Test create_or_update_organization_type when modifying generic_org_type on an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        domain_request.generic_org_type = DomainRequest.OrganizationChoices.INTERSTATE
        domain_request.save()

        # Election board should be None because interstate cannot have an election board.
        self.assertEqual(domain_request.is_election_board, None)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.INTERSTATE)

        # Try changing the org Type to something that CAN have an election board.
        domain_request_tribal = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedTribal.gov",
            generic_org_type=DomainRequest.OrganizationChoices.TRIBAL,
            is_election_board=True,
        )
        self.assertEqual(
            domain_request_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.TRIBAL_ELECTION
        )

        # Change the org type
        domain_request_tribal.generic_org_type = DomainRequest.OrganizationChoices.STATE_OR_TERRITORY
        domain_request_tribal.save()

        self.assertEqual(domain_request_tribal.is_election_board, True)
        self.assertEqual(
            domain_request_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.STATE_OR_TERRITORY_ELECTION
        )

    def test_create_or_update_organization_type_no_update(self):
        """Test create_or_update_organization_type when there are no values to update."""

        # Test for when both generic_org_type and organization_type is declared,
        # and are both non-election board
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_request.save()
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for when both generic_org_type and organization_type is declared,
        # and are both election board
        domain_request_election = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedElection.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
            organization_type=DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION,
        )

        self.assertEqual(
            domain_request_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_request_election.is_election_board, True)
        self.assertEqual(domain_request_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Modify an unrelated existing value for both, and ensure that everything is still consistent
        domain_request.city = "Fudge"
        domain_request_election.city = "Caramel"
        domain_request.save()
        domain_request_election.save()

        self.assertEqual(domain_request.city, "Fudge")
        self.assertEqual(domain_request_election.city, "Caramel")

        # Test for non-election
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for election
        self.assertEqual(
            domain_request_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_request_election.is_election_board, True)
        self.assertEqual(domain_request_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)


class TestDomainInformationCustomSave(TestCase):
    """Tests custom save behaviour on the DomainInformation object"""

    def tearDown(self):
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Domain.objects.all().delete()
        super().tearDown()

    def test_create_or_update_organization_type_new_instance(self):
        """Test create_or_update_organization_type when creating a new instance"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        domain_information = DomainInformation.create_from_da(domain_request)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

    def test_create_or_update_organization_type_new_instance_federal_does_nothing(self):
        """Test if create_or_update_organization_type does nothing when creating a new instance for federal"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            is_election_board=True,
        )

        domain_information = DomainInformation.create_from_da(domain_request)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.FEDERAL)
        self.assertEqual(domain_information.is_election_board, None)

    def test_create_or_update_organization_type_existing_instance_updates_election_board(self):
        """Test create_or_update_organization_type for an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_information = DomainInformation.create_from_da(domain_request)
        domain_information.is_election_board = True
        domain_information.save()

        self.assertEqual(domain_information.is_election_board, True)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

        # Try reverting the election board value
        domain_information.is_election_board = False
        domain_information.save()
        domain_information.refresh_from_db()

        self.assertEqual(domain_information.is_election_board, False)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

        # Try reverting setting an invalid value for election board (should revert to False)
        domain_information.is_election_board = None
        domain_information.save()

        self.assertEqual(domain_information.is_election_board, False)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

    def test_create_or_update_organization_type_existing_instance_updates_generic_org_type(self):
        """Test create_or_update_organization_type when modifying generic_org_type on an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )
        domain_information = DomainInformation.create_from_da(domain_request)

        domain_information.generic_org_type = DomainRequest.OrganizationChoices.INTERSTATE
        domain_information.save()

        # Election board should be None because interstate cannot have an election board.
        self.assertEqual(domain_information.is_election_board, None)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.INTERSTATE)

        # Try changing the org Type to something that CAN have an election board.
        domain_request_tribal = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedTribal.gov",
            generic_org_type=DomainRequest.OrganizationChoices.TRIBAL,
            is_election_board=True,
        )
        domain_information_tribal = DomainInformation.create_from_da(domain_request_tribal)
        self.assertEqual(
            domain_information_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.TRIBAL_ELECTION
        )

        # Change the org type
        domain_information_tribal.generic_org_type = DomainRequest.OrganizationChoices.STATE_OR_TERRITORY
        domain_information_tribal.save()

        self.assertEqual(domain_information_tribal.is_election_board, True)
        self.assertEqual(
            domain_information_tribal.organization_type,
            DomainRequest.OrgChoicesElectionOffice.STATE_OR_TERRITORY_ELECTION,
        )

    def test_create_or_update_organization_type_no_update(self):
        """Test create_or_update_organization_type when there are no values to update."""

        # Test for when both generic_org_type and organization_type is declared,
        # and are both non-election board
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_information = DomainInformation.create_from_da(domain_request)
        domain_information.save()
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_information.is_election_board, False)
        self.assertEqual(domain_information.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for when both generic_org_type and organization_type is declared,
        # and are both election board
        domain_request_election = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedElection.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
            organization_type=DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION,
        )
        domain_information_election = DomainInformation.create_from_da(domain_request_election)

        self.assertEqual(
            domain_information_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_information_election.is_election_board, True)
        self.assertEqual(domain_information_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Modify an unrelated existing value for both, and ensure that everything is still consistent
        domain_information.city = "Fudge"
        domain_information_election.city = "Caramel"
        domain_information.save()
        domain_information_election.save()

        self.assertEqual(domain_information.city, "Fudge")
        self.assertEqual(domain_information_election.city, "Caramel")

        # Test for non-election
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_information.is_election_board, False)
        self.assertEqual(domain_information.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for election
        self.assertEqual(
            domain_information_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_information_election.is_election_board, True)
        self.assertEqual(domain_information_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)


class TestDomainRequestIncomplete(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )
        ao, _ = Contact.objects.get_or_create(
            first_name="Meowy",
            last_name="Meoward",
            title="Chief Cat",
            email="meoward@chiefcat.com",
            phone="(206) 206 2060",
        )
        draft_domain, _ = DraftDomain.objects.get_or_create(name="MeowardMeowardMeoward.gov")
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
        alt, _ = Website.objects.get_or_create(website="MeowardMeowardMeoward1.gov")
        current, _ = Website.objects.get_or_create(website="MeowardMeowardMeoward.com")
        self.domain_request = DomainRequest.objects.create(
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            federal_type="executive",
            federal_agency=FederalAgency.objects.get(agency="AMTRAK"),
            about_your_organization="Some description",
            is_election_board=True,
            tribe_name="Some tribe name",
            organization_name="Some organization",
            address_line1="address 1",
            state_territory="CA",
            zipcode="94044",
            authorizing_official=ao,
            requested_domain=draft_domain,
            purpose="Some purpose",
            submitter=you,
            no_other_contacts_rationale=None,
            has_cisa_representative=True,
            cisa_representative_email="somerep@cisa.com",
            has_anything_else_text=True,
            anything_else="Anything else",
            is_policy_acknowledged=True,
            creator=self.user,
        )

        self.domain_request.other_contacts.add(other)
        self.domain_request.current_websites.add(current)
        self.domain_request.alternative_domains.add(alt)

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()

    def test_is_federal_complete(self):
        self.assertTrue(self.domain_request._is_federal_complete())
        self.domain_request.federal_type = None
        self.domain_request.save()
        self.assertFalse(self.domain_request._is_federal_complete())

    def test_is_interstate_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.INTERSTATE
        self.domain_request.about_your_organization = "Something something about your organization"
        self.domain_request.save()
        self.assertTrue(self.domain_request._is_interstate_complete())
        self.domain_request.about_your_organization = None
        self.domain_request.save()
        self.assertFalse(self.domain_request._is_interstate_complete())

    def test_is_state_or_territory_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.STATE_OR_TERRITORY
        self.domain_request.is_election_board = True
        self.domain_request.save()
        self.assertTrue(self.domain_request._is_state_or_territory_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        # is_election_board will overwrite to False bc of _update_org_type_from_generic_org_and_election
        self.assertTrue(self.domain_request._is_state_or_territory_complete())

    def test_is_tribal_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.TRIBAL
        self.domain_request.tribe_name = "Tribe Name"
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.domain_request._is_tribal_complete())
        self.domain_request.tribe_name = None
        self.domain_request.is_election_board = None
        self.domain_request.save()
        # is_election_board will overwrite to False bc of _update_org_type_from_generic_org_and_election
        self.assertFalse(self.domain_request._is_tribal_complete())

    def test_is_county_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.COUNTY
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.domain_request._is_county_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        # is_election_board will overwrite to False bc of _update_org_type_from_generic_org_and_election
        self.assertTrue(self.domain_request._is_county_complete())

    def test_is_city_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.CITY
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.domain_request._is_city_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        # is_election_board will overwrite to False bc of _update_org_type_from_generic_org_and_election
        self.assertTrue(self.domain_request._is_city_complete())

    def test_is_special_district_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.SPECIAL_DISTRICT
        self.domain_request.about_your_organization = "Something something about your organization"
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.domain_request._is_special_district_complete())
        self.domain_request.about_your_organization = None
        self.domain_request.is_election_board = None
        self.domain_request.save()
        # is_election_board will overwrite to False bc of _update_org_type_from_generic_org_and_election
        self.assertFalse(self.domain_request._is_special_district_complete())

    def test_is_organization_name_and_address_complete(self):
        self.assertTrue(self.domain_request._is_organization_name_and_address_complete())
        self.domain_request.organization_name = None
        self.domain_request.address_line1 = None
        self.domain_request.save()
        self.assertTrue(self.domain_request._is_organization_name_and_address_complete())

    def test_is_authorizing_official_complete(self):
        self.assertTrue(self.domain_request._is_authorizing_official_complete())
        self.domain_request.authorizing_official = None
        self.domain_request.save()
        self.assertFalse(self.domain_request._is_authorizing_official_complete())

    def test_is_requested_domain_complete(self):
        self.assertTrue(self.domain_request._is_requested_domain_complete())
        self.domain_request.requested_domain = None
        self.domain_request.save()
        self.assertFalse(self.domain_request._is_requested_domain_complete())

    def test_is_purpose_complete(self):
        self.assertTrue(self.domain_request._is_purpose_complete())
        self.domain_request.purpose = None
        self.domain_request.save()
        self.assertFalse(self.domain_request._is_purpose_complete())

    def test_is_submitter_complete(self):
        self.assertTrue(self.domain_request._is_submitter_complete())
        self.domain_request.submitter = None
        self.domain_request.save()
        self.assertFalse(self.domain_request._is_submitter_complete())

    def test_is_other_contacts_complete_missing_one_field(self):
        self.assertTrue(self.domain_request._is_other_contacts_complete())
        contact = self.domain_request.other_contacts.first()
        contact.first_name = None
        contact.save()
        self.assertFalse(self.domain_request._is_other_contacts_complete())

    def test_is_other_contacts_complete_all_none(self):
        self.domain_request.other_contacts.clear()
        self.assertFalse(self.domain_request._is_other_contacts_complete())

    def test_is_other_contacts_False_and_has_rationale(self):
        # Click radio button "No" for no other contacts and give rationale
        self.domain_request.other_contacts.clear()
        self.domain_request.other_contacts.exists = False
        self.domain_request.no_other_contacts_rationale = "Some rationale"
        self.assertTrue(self.domain_request._is_other_contacts_complete())

    def test_is_other_contacts_False_and_NO_rationale(self):
        # Click radio button "No" for no other contacts and DONT give rationale
        self.domain_request.other_contacts.clear()
        self.domain_request.other_contacts.exists = False
        self.domain_request.no_other_contacts_rationale = None
        self.assertFalse(self.domain_request._is_other_contacts_complete())

    def test_is_additional_details_complete(self):
        test_cases = [
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - Yes
            # Anything Else Radio - Yes
            # Anything Else Text - Yes
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": "some@cisarepemail.com",
                "has_anything_else_text": True,
                "anything_else": "Some text",
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - Yes
            # Anything Else Radio - Yes
            # Anything Else Text - None
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": "some@cisarepemail.com",
                "has_anything_else_text": True,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - None >> e-mail is optional so it should not change anything setting this to None
            # Anything Else Radio - No
            # Anything Else Text - No
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": None,
                "has_anything_else_text": False,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - None
            # Anything Else Radio - None
            # Anything Else Text - None
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                "expected": False,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - None
            # Anything Else Text - None
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                "expected": False,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - No
            # Anything Else Text - No
            # sync_yes_no will override has_cisa_representative to be False if cisa_representative_first_name is None
            # therefore, our expected will be True
            {
                "has_cisa_representative": True,
                # Above will be overridden to False if cisa_representative_first_name is None
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": False,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - Yes
            # Anything Else Text - None
            # NOTE: We should never have an instance where only firstname or only lastname are populated
            # (they are both required)
            {
                "has_cisa_representative": True,
                # Above will be overridden to False if cisa_representative_first_name is None or
                # cisa_representative_last_name is None bc of sync_yes_no_form_fields
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - Yes
            # Anything Else Text - Yes
            {
                "has_cisa_representative": True,
                # Above will be overridden to False if cisa_representative_first_name is None or
                # cisa_representative_last_name is None bc of sync_yes_no_form_fields
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": "Some text",
                "expected": True,
            },
            # CISA Rep - No
            # Anything Else Radio - Yes
            # Anything Else Text - Yes
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": "Some text",
                "expected": True,
            },
            # CISA Rep - No
            # Anything Else Radio - Yes
            # Anything Else Text - None
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - No
            # Anything Else Radio - None
            # Anything Else Text - None
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                # Above is both None, so it does NOT get overwritten
                "expected": False,
            },
            # CISA Rep - No
            # Anything Else Radio - No
            # Anything Else Text - No
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": False,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - None
            # Anything Else Radio - None
            {
                "has_cisa_representative": None,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                "expected": False,
            },
        ]
        for case in test_cases:
            with self.subTest(case=case):
                self.domain_request.has_cisa_representative = case["has_cisa_representative"]
                self.domain_request.cisa_representative_email = case["cisa_representative_email"]
                self.domain_request.has_anything_else_text = case["has_anything_else_text"]
                self.domain_request.anything_else = case["anything_else"]
                self.domain_request.save()
                self.domain_request.refresh_from_db()
                self.assertEqual(
                    self.domain_request._is_additional_details_complete(),
                    case["expected"],
                    msg=f"Failed for case: {case}",
                )

    def test_is_policy_acknowledgement_complete(self):
        self.assertTrue(self.domain_request._is_policy_acknowledgement_complete())
        self.domain_request.is_policy_acknowledged = False
        self.assertTrue(self.domain_request._is_policy_acknowledgement_complete())
        self.domain_request.is_policy_acknowledged = None
        self.assertFalse(self.domain_request._is_policy_acknowledgement_complete())

    def test_form_complete(self):
        request = self.factory.get("/")
        request.user = self.user

        self.assertTrue(self.domain_request._form_complete(request))
        self.domain_request.generic_org_type = None
        self.domain_request.save()
        self.assertFalse(self.domain_request._form_complete(request))
