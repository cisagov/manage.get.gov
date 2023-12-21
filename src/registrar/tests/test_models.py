from django.test import TestCase
from django.db.utils import IntegrityError
from unittest.mock import patch

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

import boto3_mocking
from registrar.models.transition_domain import TransitionDomain  # type: ignore
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
        self.assertEqual(application.status, DomainApplication.ApplicationStatus.STARTED)

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
        application = DomainApplication.objects.create(creator=user, requested_domain=site)
        # no submitter email so this emits a log warning
        with less_console_noise():
            application.submit()
        self.assertEqual(application.status, application.ApplicationStatus.SUBMITTED)

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

        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_in_review_submitted(self):
        """Create an application with status in review and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.IN_REVIEW)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_approved_submitted(self):
        """Create an application with status approved and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_rejected_submitted(self):
        """Create an application with status rejected and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.REJECTED)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_ineligible_submitted(self):
        """Create an application with status ineligible and call submit
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.INELIGIBLE)

        with self.assertRaises(TransitionNotAllowed):
            application.submit()

    def test_transition_not_allowed_started_in_review(self):
        """Create an application with status started and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_in_review_in_review(self):
        """Create an application with status in review and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.IN_REVIEW)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_approved_in_review(self):
        """Create an application with status approved and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_action_needed_in_review(self):
        """Create an application with status action needed and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_rejected_in_review(self):
        """Create an application with status rejected and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.REJECTED)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_withdrawn_in_review(self):
        """Create an application with status withdrawn and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_ineligible_in_review(self):
        """Create an application with status ineligible and call in_review
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.INELIGIBLE)

        with self.assertRaises(TransitionNotAllowed):
            application.in_review()

    def test_transition_not_allowed_started_action_needed(self):
        """Create an application with status started and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_submitted_action_needed(self):
        """Create an application with status submitted and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_action_needed_action_needed(self):
        """Create an application with status action needed and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_approved_action_needed(self):
        """Create an application with status approved and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_withdrawn_action_needed(self):
        """Create an application with status withdrawn and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_ineligible_action_needed(self):
        """Create an application with status ineligible and call action_needed
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.INELIGIBLE)

        with self.assertRaises(TransitionNotAllowed):
            application.action_needed()

    def test_transition_not_allowed_started_approved(self):
        """Create an application with status started and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_approved_approved(self):
        """Create an application with status approved and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_action_needed_approved(self):
        """Create an application with status action needed and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_withdrawn_approved(self):
        """Create an application with status withdrawn and call approve
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.approve()

    def test_transition_not_allowed_started_withdrawn(self):
        """Create an application with status started and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_approved_withdrawn(self):
        """Create an application with status approved and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_action_needed_withdrawn(self):
        """Create an application with status action needed and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_rejected_withdrawn(self):
        """Create an application with status rejected and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.REJECTED)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_withdrawn_withdrawn(self):
        """Create an application with status withdrawn and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_ineligible_withdrawn(self):
        """Create an application with status ineligible and call withdraw
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.INELIGIBLE)

        with self.assertRaises(TransitionNotAllowed):
            application.withdraw()

    def test_transition_not_allowed_started_rejected(self):
        """Create an application with status started and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_submitted_rejected(self):
        """Create an application with status submitted and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_action_needed_rejected(self):
        """Create an application with status action needed and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_withdrawn_rejected(self):
        """Create an application with status withdrawn and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_rejected_rejected(self):
        """Create an application with status rejected and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.REJECTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_ineligible_rejected(self):
        """Create an application with status ineligible and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.INELIGIBLE)

        with self.assertRaises(TransitionNotAllowed):
            application.reject()

    def test_transition_not_allowed_approved_rejected_when_domain_is_active(self):
        """Create an application with status approved, create a matching domain that
        is active, and call reject against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED)
        domain = Domain.objects.create(name=application.requested_domain.name)
        application.approved_domain = domain
        application.save()

        # Define a custom implementation for is_active
        def custom_is_active(self):
            return True  # Override to return True

        # Use patch to temporarily replace is_active with the custom implementation
        with patch.object(Domain, "is_active", custom_is_active):
            # Now, when you call is_active on Domain, it will return True
            with self.assertRaises(TransitionNotAllowed):
                application.reject()

    def test_transition_not_allowed_started_ineligible(self):
        """Create an application with status started and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.STARTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject_with_prejudice()

    def test_transition_not_allowed_submitted_ineligible(self):
        """Create an application with status submitted and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject_with_prejudice()

    def test_transition_not_allowed_action_needed_ineligible(self):
        """Create an application with status action needed and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.ACTION_NEEDED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject_with_prejudice()

    def test_transition_not_allowed_withdrawn_ineligible(self):
        """Create an application with status withdrawn and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.WITHDRAWN)

        with self.assertRaises(TransitionNotAllowed):
            application.reject_with_prejudice()

    def test_transition_not_allowed_rejected_ineligible(self):
        """Create an application with status rejected and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.REJECTED)

        with self.assertRaises(TransitionNotAllowed):
            application.reject_with_prejudice()

    def test_transition_not_allowed_ineligible_ineligible(self):
        """Create an application with status ineligible and call reject
        against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.INELIGIBLE)

        with self.assertRaises(TransitionNotAllowed):
            application.reject_with_prejudice()

    def test_transition_not_allowed_approved_ineligible_when_domain_is_active(self):
        """Create an application with status approved, create a matching domain that
        is active, and call reject_with_prejudice against transition rules"""

        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED)
        domain = Domain.objects.create(name=application.requested_domain.name)
        application.approved_domain = domain
        application.save()

        # Define a custom implementation for is_active
        def custom_is_active(self):
            return True  # Override to return True

        # Use patch to temporarily replace is_active with the custom implementation
        with patch.object(Domain, "is_active", custom_is_active):
            # Now, when you call is_active on Domain, it will return True
            with self.assertRaises(TransitionNotAllowed):
                application.reject_with_prejudice()


class TestPermissions(TestCase):

    """Test the User-Domain-Role connection."""

    def test_approval_creates_role(self):
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user, requested_domain=draft_domain)
        # skip using the submit method
        application.status = DomainApplication.ApplicationStatus.SUBMITTED
        application.approve()

        # should be a role for this user
        domain = Domain.objects.get(name="igorville.gov")
        self.assertTrue(UserDomainRole.objects.get(user=user, domain=domain))


class TestDomainInfo(TestCase):

    """Test creation of Domain Information when approved."""

    def test_approval_creates_info(self):
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user, requested_domain=draft_domain)
        # skip using the submit method
        application.status = DomainApplication.ApplicationStatus.SUBMITTED
        application.approve()

        # should be an information present for this domain
        domain = Domain.objects.get(name="igorville.gov")
        self.assertTrue(DomainInformation.objects.get(domain=domain))


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

    def tearDown(self):
        super().tearDown()
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
