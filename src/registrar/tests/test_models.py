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
from unittest import skip

import boto3_mocking  # type: ignore
from .common import MockSESClient, less_console_noise, completed_application
from unittest.mock import patch, MagicMock
from django.conf import settings

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

    def test_status_change_to_invetigating_sends_email(self):
        """Create an application and change its status to investigating,
        trigger email send and test the email."""

        application = completed_application(status=DomainApplication.SUBMITTED)

        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            # Mock the model's save method
            with patch("registrar.models.DomainApplication.save") as mock_save:
                # Set the return value of the save method
                mock_save.return_value = None

                # Perform the model change (e.g., update a field)
                application.status = DomainApplication.INVESTIGATING
                application.save()

                # Trigger the email
                application._send_in_review_email()

                # Assert that the save method was called
                mock_save.assert_called_once()

                # Access the arguments passed to send_email
                call_args = mock_client_instance.send_email.call_args
                args, kwargs = call_args

                # Retrieve the email details from the arguments
                from_email = kwargs.get("FromEmailAddress")
                to_email = kwargs["Destination"]["ToAddresses"][0]
                email_content = kwargs["Content"]
                email_body = email_content["Simple"]["Body"]["Text"]["Data"]

                # Assert or perform other checks on the email details
                expected_string = "Your .gov domain request is being reviewed"
                self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
                self.assertEqual(to_email, EMAIL)
                self.assertIn(expected_string, email_body)

                # Perform assertions on the mock call itself
                mock_client_instance.send_email.assert_called_once()

                # Cleanup
                application.delete()


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


@skip("Not implemented yet.")
class TestDomainApplicationLifeCycle(TestCase):
    def test_application_approval(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # analyst approves DomainApplication
        # test: Domain is activated
        pass

    def test_application_rejection(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # analyst rejects DomainApplication
        # test: Domain remains inactive
        pass

    def test_application_deleted_before_approval(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # admin deletes DomainApplication
        # test: Domain is deleted; Hosts, HostIps and Nameservers are deleted
        pass

    def test_application_deleted_following_approval(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # analyst approves DomainApplication
        # admin deletes DomainApplication
        # test: DomainApplication foreign key field on Domain is set to null
        pass

    def test_application_approval_with_conflicting_name(self):
        # DomainApplication #1 is created
        # test: Domain #1 is created and is inactive
        # analyst approves DomainApplication #1
        # test: Domain #1 is activated
        # DomainApplication #2 is created, with the same domain name string
        # test: Domain #2 is created and is inactive
        # analyst approves DomainApplication #2
        # test: error is raised
        # test: DomainApplication #1 remains approved
        # test: Domain #1 remains active
        # test: DomainApplication #2 remains in investigating
        # test: Domain #2 remains inactive
        pass

    def test_application_approval_with_network_errors(self):
        # TODO: scenario wherein application is approved,
        # but attempts to contact the registry to activate the domain fail
        pass
