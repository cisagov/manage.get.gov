from unittest import skip
from unittest.mock import MagicMock, ANY, patch

from django.conf import settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from .common import MockSESClient, create_user  # type: ignore
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
    DomainInvitation,
    Contact,
    PublicContact,
    Host,
    HostIP,
    UserDomainRole,
    User,
)
from datetime import date, datetime, timedelta
from django.utils import timezone

from .common import less_console_noise
from .test_views import TestWithUser

import logging

logger = logging.getLogger(__name__)


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
        with less_console_noise():
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
        with less_console_noise():
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
        with less_console_noise():
            self.user.status = User.RESTRICTED
            self.user.save()
            home_page = self.app.get("/")
            self.assertContains(home_page, "igorville.gov")
            response = self.client.get(reverse("domain", kwargs={"pk": self.domain.id}))
            self.assertEqual(response.status_code, 403)

    def test_domain_detail_allowed_for_on_hold(self):
        """Test that the domain overview page displays for on hold domain"""
        with less_console_noise():
            home_page = self.app.get("/")
            self.assertContains(home_page, "on-hold.gov")

            # View domain overview page
            detail_page = self.client.get(reverse("domain", kwargs={"pk": self.domain_on_hold.id}))
            self.assertNotContains(detail_page, "Edit")

    def test_domain_detail_see_just_nameserver(self):
        with less_console_noise():
            home_page = self.app.get("/")
            self.assertContains(home_page, "justnameserver.com")

            # View nameserver on Domain Overview page
            detail_page = self.app.get(reverse("domain", kwargs={"pk": self.domain_just_nameserver.id}))

            self.assertContains(detail_page, "justnameserver.com")
            self.assertContains(detail_page, "ns1.justnameserver.com")
            self.assertContains(detail_page, "ns2.justnameserver.com")

    def test_domain_detail_see_nameserver_and_ip(self):
        with less_console_noise():
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
        with less_console_noise():
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
        with less_console_noise():
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
        with less_console_noise():
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
        with less_console_noise():
            page = self.client.get(reverse("domain-security-email", kwargs={"pk": self.domain.id}))
            self.assertContains(page, "Security email")

    def test_domain_security_email_form(self):
        """Adding a security email works.
        Uses self.app WebTest because we need to interact with forms.
        """
        with less_console_noise():
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

    def test_domain_security_email_form_messages(self):
        """
        Test against the success and error messages that are defined in the view
        """
        with less_console_noise():
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
