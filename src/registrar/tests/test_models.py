from django.test import TestCase
from django.db.utils import IntegrityError

from registrar.models import (
    Contact,
    DomainApplication,
    DomainInformation,
    User,
    Website,
    Domain,
    DraftDomain,
    DomainInvitation,
    UserDomainRole,
)

import boto3_mocking  # type: ignore
from .common import MockSESClient, less_console_noise, completed_application
from django_fsm import TransitionNotAllowed

boto3_mocking.clients.register_handler("sesv2", MockSESClient)


# The DomainApplication submit method has a side effect of sending an email
# with AWS SES, so mock that out in all of these test cases
@boto3_mocking.patching
class TestDomainApplication(TestCase):
    def test_empty_create_fails(self):
        """Can't create a completely empty domain application."""
        with self.assertRaisesRegex(IntegrityError, "creator"):
            DomainApplication.objects.create()

    def test_minimal_create(self):
        """Can create with just a creator."""
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user)
        self.assertEqual(application.status, DomainApplication.STARTED)

    def test_full_create(self):
        """Can create with all fields."""
        user, _ = User.objects.get_or_create()
        contact = Contact.objects.create()
        com_website, _ = Website.objects.get_or_create(website="igorville.com")
        gov_website, _ = Website.objects.get_or_create(website="igorville.gov")
        domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=user,
            investigator=user,
            organization_type=DomainApplication.OrganizationChoices.FEDERAL,
            federal_type=DomainApplication.BranchChoices.EXECUTIVE,
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
        application.current_websites.add(com_website)
        application.alternative_domains.add(gov_website)
        application.other_contacts.add(contact)
        application.save()

    def test_domain_info(self):
        """Can create domain info with all fields."""
        user, _ = User.objects.get_or_create()
        contact = Contact.objects.create()
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        information = DomainInformation.objects.create(
            creator=user,
            organization_type=DomainInformation.OrganizationChoices.FEDERAL,
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
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user)
        with self.assertRaises(ValueError):
            # can't submit an application with a null domain name
            application.submit()

    def test_status_fsm_submit_succeed(self):
        user, _ = User.objects.get_or_create()
        site = DraftDomain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=user, requested_domain=site
        )
        # no submitter email so this emits a log warning
        with less_console_noise():
            application.submit()
        self.assertEqual(application.status, application.SUBMITTED)

    def test_submit_sends_email(self):
        """Create an application and submit it and see if email was sent."""
        user, _ = User.objects.get_or_create()
        contact = Contact.objects.create(email="test@test.gov")
        domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=user,
            requested_domain=domain,
            submitter=contact,
        )
        application.save()
        application.submit()

        # check to see if an email was sent
        self.assertGreater(
            len(
                [
                    email
                    for email in MockSESClient.EMAILS_SENT
                    if "test@test.gov" in email["kwargs"]["Destination"]["ToAddresses"]
                ]
            ),
            0,
        )

    def test_transition_not_allowed_submitted_submitted(self):
        """Create an application with status submitted and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.SUBMITTED)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_in_review_submitted(self):
        """Create an application with status in review and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.IN_REVIEW)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_approved_submitted(self):
        """Create an application with status approved and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_rejected_submitted(self):
        """Create an application with status rejected and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.FRIEDEGGS)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_started_in_review(self):
        """Create an application with status started and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_in_review_in_review(self):
        """Create an application with status in review and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.IN_REVIEW)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_approved_in_review(self):
        """Create an application with status approved and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_action_needed_in_review(self):
        """Create an application with status action needed and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_rejected_in_review(self):
        """Create an application with status rejected and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.FRIEDEGGS)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_withdrawn_in_review(self):
        """Create an application with status withdrawn and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_started_action_needed(self):
        """Create an application with status started and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_submitted_action_needed(self):
        """Create an application with status submitted and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.SUBMITTED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_action_needed_action_needed(self):
        """Create an application with status action needed and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_approved_action_needed(self):
        """Create an application with status approved and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_withdrawn_action_needed(self):
        """Create an application with status withdrawn and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_started_approved(self):
        """Create an application with status started and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_approved_approved(self):
        """Create an application with status approved and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_action_needed_approved(self):
        """Create an application with status action needed and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_withdrawn_approved(self):
        """Create an application with status withdrawn and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_started_withdrawn(self):
        """Create an application with status started and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_approved_withdrawn(self):
        """Create an application with status approved and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_action_needed_withdrawn(self):
        """Create an application with status action needed and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_rejected_withdrawn(self):
        """Create an application with status rejected and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.FRIEDEGGS)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_withdrawn_withdrawn(self):
        """Create an application with status withdrawn and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_started_rejected(self):
        """Create an application with status started and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_submitted_rejected(self):
        """Create an application with status submitted and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.SUBMITTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_action_needed_rejected(self):
        """Create an application with status action needed and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_withdrawn_rejected(self):
        """Create an application with status withdrawn and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_rejected_rejected(self):
        """Create an application with status rejected and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.FRIEDEGGS)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()


class TestPermissions(TestCase):

    """Test the User-Domain-Role connection."""

    def test_approval_creates_role(self):
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(
            creator=user, requested_domain=draft_domain
        )
        # skip using the submit method
        application.status = DomainApplication.SUBMITTED
        application.approve()

        # should be a role for this user
        domain = Domain.objects.get(name="igorville.gov")
        self.assertTrue(UserDomainRole.objects.get(user=user, domain=domain))


class TestDomainInfo(TestCase):

    """Test creation of Domain Information when approved."""

    def test_approval_creates_info(self):
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(
            creator=user, requested_domain=draft_domain
        )
        # skip using the submit method
        application.status = DomainApplication.SUBMITTED
        application.approve()

        # should be an information present for this domain
        domain = Domain.objects.get(name="igorville.gov")
        self.assertTrue(DomainInformation.objects.get(domain=domain))


class TestInvitations(TestCase):

    """Test the retrieval of invitations."""

    def setUp(self):
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.email = "mayor@igorville.gov"
        self.invitation, _ = DomainInvitation.objects.get_or_create(
            email=self.email, domain=self.domain
        )
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
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.ADMIN
        )
        # this is not an error but does produce a console warning
        with less_console_noise():
            self.invitation.retrieve()
        self.assertEqual(self.invitation.status, DomainInvitation.RETRIEVED)

    def test_retrieve_on_first_login(self):
        """A new user's first_login callback retrieves their invitations."""
        self.user.first_login()
        self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))
