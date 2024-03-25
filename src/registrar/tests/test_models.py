from django.test import TestCase
from django.db.utils import IntegrityError
from unittest.mock import patch

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
)

import boto3_mocking
from registrar.models.transition_domain import TransitionDomain
from registrar.models.verified_by_staff import VerifiedByStaff  # type: ignore
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
                federal_type=DomainRequest.BranchChoices.EXECUTIVE,
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
                federal_type=DomainInformation.BranchChoices.EXECUTIVE,
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


class TestContact(TestCase):
    def setUp(self):
        self.email_for_invalid = "intern@igorville.gov"
        self.invalid_user, _ = User.objects.get_or_create(
            username=self.email_for_invalid, email=self.email_for_invalid, first_name="", last_name=""
        )
        self.invalid_contact, _ = Contact.objects.get_or_create(user=self.invalid_user)

        self.email = "mayor@igorville.gov"
        self.user, _ = User.objects.get_or_create(email=self.email, first_name="Jeff", last_name="Lebowski")
        self.contact, _ = Contact.objects.get_or_create(user=self.user)

        self.contact_as_ao, _ = Contact.objects.get_or_create(email="newguy@igorville.gov")
        self.domain_request = DomainRequest.objects.create(creator=self.user, authorizing_official=self.contact_as_ao)

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()
        User.objects.all().delete()

    def test_saving_contact_updates_user_first_last_names(self):
        """When a contact is updated, we propagate the changes to the linked user if it exists."""

        # User and Contact are created and linked as expected.
        # An empty User object should create an empty contact.
        self.assertEqual(self.invalid_contact.first_name, "")
        self.assertEqual(self.invalid_contact.last_name, "")
        self.assertEqual(self.invalid_user.first_name, "")
        self.assertEqual(self.invalid_user.last_name, "")

        # Manually update the contact - mimicking production (pre-existing data)
        self.invalid_contact.first_name = "Joey"
        self.invalid_contact.last_name = "Baloney"
        self.invalid_contact.save()

        # Refresh the user object to reflect the changes made in the database
        self.invalid_user.refresh_from_db()

        # Updating the contact's first and last names propagate to the user
        self.assertEqual(self.invalid_contact.first_name, "Joey")
        self.assertEqual(self.invalid_contact.last_name, "Baloney")
        self.assertEqual(self.invalid_user.first_name, "Joey")
        self.assertEqual(self.invalid_user.last_name, "Baloney")

    def test_saving_contact_does_not_update_user_first_last_names(self):
        """When a contact is updated, we avoid propagating the changes to the linked user if it already has a value"""

        # User and Contact are created and linked as expected
        self.assertEqual(self.contact.first_name, "Jeff")
        self.assertEqual(self.contact.last_name, "Lebowski")
        self.assertEqual(self.user.first_name, "Jeff")
        self.assertEqual(self.user.last_name, "Lebowski")

        self.contact.first_name = "Joey"
        self.contact.last_name = "Baloney"
        self.contact.save()

        # Refresh the user object to reflect the changes made in the database
        self.user.refresh_from_db()

        # Updating the contact's first and last names propagate to the user
        self.assertEqual(self.contact.first_name, "Joey")
        self.assertEqual(self.contact.last_name, "Baloney")
        self.assertEqual(self.user.first_name, "Jeff")
        self.assertEqual(self.user.last_name, "Lebowski")

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
