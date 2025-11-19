"""Test our email templates and sending."""

from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.utils import timezone

from waffle.testutils import override_flag
from registrar.utility import email
from registrar.utility.email import send_templated_email

from .common import completed_domain_request
from registrar.models import AllowedEmail, Domain, User, DomainInformation
from registrar.models.portfolio import Portfolio
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices

from api.tests.common import less_console_noise_decorator
from datetime import datetime, date, timedelta

import boto3_mocking  # type: ignore


class TestEmails(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        allowed_emails = [
            AllowedEmail(email="doesnotexist@igorville.com"),
            AllowedEmail(email="testy@town.com"),
            AllowedEmail(email="mayor@igorville.gov"),
            AllowedEmail(email="testy2@town.com"),
            AllowedEmail(email="cisaRep@igorville.gov"),
            AllowedEmail(email="sender@example.com"),
            AllowedEmail(email="recipient@example.com"),
        ]
        AllowedEmail.objects.bulk_create(allowed_emails)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        AllowedEmail.objects.all().delete()

    def setUp(self):
        self.mock_client_class = MagicMock()
        self.mock_client = self.mock_client_class.return_value

    def tearDown(self):
        super().tearDown()

    @boto3_mocking.patching
    @override_flag("disable_email_sending", active=True)
    @less_console_noise_decorator
    def test_disable_email_flag(self):
        """Test if the 'disable_email_sending' stops emails from being sent"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            expected_message = "Email sending is disabled due to"
            with self.assertRaisesRegex(email.EmailSendingError, expected_message):
                send_templated_email(
                    "test content",
                    "test subject",
                    "doesnotexist@igorville.com",
                    context={"domain_request": self},
                    bcc_address=None,
                )

        # Assert that an email wasn't sent
        self.assertFalse(self.mock_client.send_email.called)

    @boto3_mocking.patching
    def test_email_with_cc(self):
        """Test sending email with cc works"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            send_templated_email(
                "emails/update_to_approved_domain.txt",
                "emails/update_to_approved_domain_subject.txt",
                "doesnotexist@igorville.com",
                context={"domain": "test", "user": "test", "date": 1, "changes": "test"},
                bcc_address=None,
                cc_addresses=["testy2@town.com", "mayor@igorville.gov"],
            )

        # check that an email was sent
        self.assertTrue(self.mock_client.send_email.called)

        # check the call sequence for the email
        args, kwargs = self.mock_client.send_email.call_args
        self.assertIn("Destination", kwargs)
        self.assertIn("CcAddresses", kwargs["Destination"])

        self.assertEqual(["testy2@town.com", "mayor@igorville.gov"], kwargs["Destination"]["CcAddresses"])

    @boto3_mocking.patching
    @override_settings(IS_PRODUCTION=True)
    def test_email_with_cc_in_prod(self):
        """Test sending email with cc works in prod"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            send_templated_email(
                "emails/update_to_approved_domain.txt",
                "emails/update_to_approved_domain_subject.txt",
                "doesnotexist@igorville.com",
                context={"domain": "test", "user": "test", "date": 1, "changes": "test"},
                bcc_address=None,
                cc_addresses=["testy2@town.com", "mayor@igorville.gov"],
            )

        # check that an email was sent
        self.assertTrue(self.mock_client.send_email.called)

        # check the call sequence for the email
        args, kwargs = self.mock_client.send_email.call_args
        self.assertIn("Destination", kwargs)
        self.assertIn("CcAddresses", kwargs["Destination"])

        self.assertEqual(["testy2@town.com", "mayor@igorville.gov"], kwargs["Destination"]["CcAddresses"])

    @boto3_mocking.patching
    @override_settings(IS_PRODUCTION=True, BASE_URL="manage.get.gov")
    def test_email_production_subject_and_url_check(self):
        """Test sending an email in production that:
        1. Does not have a prefix in the email subject (no [MANAGE])
        2. Uses the production URL in the email body of manage.get.gov still"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            send_templated_email(
                "emails/update_to_approved_domain.txt",
                "emails/update_to_approved_domain_subject.txt",
                "doesnotexist@igorville.com",
                context={"domain": "test", "user": "test", "date": 1, "changes": "test"},
                bcc_address=None,
                cc_addresses=["testy2@town.com", "mayor@igorville.gov"],
            )

        # check that an email was sent
        self.assertTrue(self.mock_client.send_email.called)

        # check the call sequence for the email
        args, kwargs = self.mock_client.send_email.call_args
        self.assertIn("Destination", kwargs)
        self.assertIn("CcAddresses", kwargs["Destination"])

        self.assertEqual(["testy2@town.com", "mayor@igorville.gov"], kwargs["Destination"]["CcAddresses"])

        # Grab email subject
        email_subject = kwargs["Content"]["Simple"]["Subject"]["Data"]

        # Check that the subject does NOT contain a prefix for production
        self.assertNotIn("[MANAGE]", email_subject)
        self.assertIn("An update was made to", email_subject)

        # Grab email body
        email_body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]

        # Check that manage_url is correctly set for production
        self.assertIn("https://manage.get.gov", email_body)

    @boto3_mocking.patching
    @override_settings(IS_PRODUCTION=False, BASE_URL="https://getgov-rh.app.cloud.gov")
    def test_email_non_production_subject_and_url_check(self):
        """Test sending an email in production that:
        1. Does prefix in the email subject (ie [GETGOV-RH])
        2. Uses the sandbox url in the email body (ie getgov-rh.app.cloud.gov)"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            send_templated_email(
                "emails/update_to_approved_domain.txt",
                "emails/update_to_approved_domain_subject.txt",
                "doesnotexist@igorville.com",
                context={"domain": "test", "user": "test", "date": 1, "changes": "test"},
                bcc_address=None,
                cc_addresses=["testy2@town.com", "mayor@igorville.gov"],
            )

        # check that an email was sent
        self.assertTrue(self.mock_client.send_email.called)

        # check the call sequence for the email
        args, kwargs = self.mock_client.send_email.call_args
        self.assertIn("Destination", kwargs)
        self.assertIn("CcAddresses", kwargs["Destination"])
        self.assertEqual(["testy2@town.com", "mayor@igorville.gov"], kwargs["Destination"]["CcAddresses"])

        # Grab email subject
        email_subject = kwargs["Content"]["Simple"]["Subject"]["Data"]

        # Check that the subject DOES contain a prefix of the current sandbox
        self.assertIn("[GETGOV-RH]", email_subject)

        # Grab email body
        email_body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]

        # Check that manage_url is correctly set of the sandbox
        self.assertIn("https://getgov-rh.app.cloud.gov", email_body)

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation(self):
        """Submission confirmation email works."""
        domain_request = completed_domain_request(user=User.objects.create(username="test", email="testy@town.com"))

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()

        # check that an email was sent
        self.assertTrue(self.mock_client.send_email.called)

        # check the call sequence for the email
        args, kwargs = self.mock_client.send_email.call_args
        self.assertIn("Content", kwargs)
        self.assertIn("Simple", kwargs["Content"])
        self.assertIn("Subject", kwargs["Content"]["Simple"])
        self.assertIn("Body", kwargs["Content"]["Simple"])

        # check for things in the email content (not an exhaustive list)
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]

        self.assertIn("Type of organization:", body)
        self.assertIn("Federal", body)
        self.assertIn("Senior official:", body)
        self.assertIn("Testy Tester", body)
        self.assertIn(".gov domain:", body)
        self.assertIn("city.gov", body)
        self.assertIn("city1.gov", body)

        # check for optional things
        self.assertIn("Other employees from your organization:", body)
        self.assertIn("Current websites:", body)
        self.assertIn("city.com", body)
        self.assertIn("About your organization:", body)
        self.assertIn("Anything else", body)

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_no_current_website_spacing(self):
        """Test line spacing without current_website."""
        domain_request = completed_domain_request(
            current_websites=[], user=User.objects.create(username="test", email="testy@town.com")
        )
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("Current websites:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5555\n\n.gov domain:")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_current_website_spacing(self):
        """Test line spacing with current_website."""
        domain_request = completed_domain_request(user=User.objects.create(username="test", email="testy@town.com"))
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("Current websites:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5555\n\nCurrent websites:")
        self.assertRegex(body, r"city.com\n\n.gov domain:")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_other_contacts_spacing(self):
        """Test line spacing with other contacts."""

        # Create fake requester
        _requester = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
            phone="(888) 888 8888",
            email="testy@town.com",
        )

        # Create a fake domain request
        domain_request = completed_domain_request(has_other_contacts=True, user=_requester)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("Other employees from your organization:", body)
        self.assertRegex(body, r"8888\n\nOther employees")
        self.assertRegex(body, r"5557\n\nAnything else")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_no_other_contacts_spacing(self):
        """Test line spacing without other contacts."""
        domain_request = completed_domain_request(
            has_other_contacts=False, user=User.objects.create(username="test", email="testy@town.com")
        )
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"None\n\nAnything else")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_alternative_govdomain_spacing(self):
        """Test line spacing with alternative .gov domain."""
        domain_request = completed_domain_request(user=User.objects.create(username="test", email="testy@town.com"))
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("city1.gov", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"city.gov\n\nAlternative domains:\ncity1.gov\n\nPurpose of your domain:")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_no_alternative_govdomain_spacing(self):
        """Test line spacing without alternative .gov domain."""
        domain_request = completed_domain_request(
            alternative_domains=[], user=User.objects.create(username="test", email="testy@town.com")
        )
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("city1.gov", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"city.gov\n\nPurpose of your domain:")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_about_your_organization_spacing(self):
        """Test line spacing with about your organization."""
        domain_request = completed_domain_request(
            has_about_your_organization=True, user=User.objects.create(username="test", email="testy@town.com")
        )
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("About your organization:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"10002\n\nAbout your organization:")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_no_about_your_organization_spacing(self):
        """Test line spacing without about your organization."""
        domain_request = completed_domain_request(
            has_about_your_organization=False, user=User.objects.create(username="test", email="testy@town.com")
        )
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("About your organization:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"10002\n\nSenior official:")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_anything_else_spacing(self):
        """Test line spacing with anything else."""
        domain_request = completed_domain_request(
            has_anything_else=True, user=User.objects.create(username="test", email="testy@town.com")
        )
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5557\n\nAnything else?")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_submission_confirmation_no_anything_else_spacing(self):
        """Test line spacing without anything else."""
        domain_request = completed_domain_request(
            has_anything_else=False, user=User.objects.create(username="test", email="testy@town.com")
        )
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("Anything else", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5557\n\n----")

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_send_email_with_attachment(self):
        with boto3_mocking.clients.handler_for("ses", self.mock_client_class):
            sender_email = "sender@example.com"
            recipient_email = "recipient@example.com"
            subject = "Test Subject"
            body = "Test Body"
            attachment_file = b"Attachment file content"
            current_date = datetime.now().strftime("%m%d%Y")
            current_filename = f"domain-metadata-{current_date}.zip"

            email.send_email_with_attachment(
                sender_email, recipient_email, subject, body, attachment_file, self.mock_client
            )
            # Assert that the `send_raw_email` method of the mocked SES client was called with the expected params
            self.mock_client.send_raw_email.assert_called_once()

            # Get the args passed to the `send_raw_email` method
            call_args = self.mock_client.send_raw_email.call_args[1]

            # Assert that the attachment filename is correct
            self.assertEqual(call_args["RawMessage"]["Data"].count(f'filename="{current_filename}"'), 1)

            # Assert that the attachment content is encrypted
            self.assertIn("Content-Type: application/octet-stream", call_args["RawMessage"]["Data"])
            self.assertIn("Content-Transfer-Encoding: base64", call_args["RawMessage"]["Data"])
            self.assertIn("Content-Disposition: attachment;", call_args["RawMessage"]["Data"])
            self.assertNotIn("Attachment file content", call_args["RawMessage"]["Data"])


class TestAllowedEmail(TestCase):
    """Tests our allowed email whitelist"""

    def setUp(self):
        self.mock_client_class = MagicMock()
        self.mock_client = self.mock_client_class.return_value
        self.email = "mayor@igorville.gov"
        self.email_2 = "cake@igorville.gov"
        self.plus_email = "mayor+1@igorville.gov"
        self.invalid_plus_email = "1+mayor@igorville.gov"

    def tearDown(self):
        super().tearDown()
        AllowedEmail.objects.all().delete()

    @boto3_mocking.patching
    @override_settings(IS_PRODUCTION=True)
    @less_console_noise_decorator
    def test_email_whitelist_disabled_in_production(self):
        """Tests if the whitelist is disabled in production"""

        # Ensure that the given email isn't in the whitelist
        is_in_whitelist = AllowedEmail.objects.filter(email=self.email).exists()
        self.assertFalse(is_in_whitelist)

        # The submit should work as normal
        domain_request = completed_domain_request(has_anything_else=False)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("Anything else", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5557\n\n----")

    @boto3_mocking.patching
    @override_settings(IS_PRODUCTION=False)
    @less_console_noise_decorator
    def test_email_allowlist(self):
        """Tests the email allowlist is enabled elsewhere"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            expected_message = "Could not send email. "
            "The email 'doesnotexist@igorville.com' does not exist within the allow list."
            with self.assertRaisesRegex(email.EmailSendingError, expected_message):
                send_templated_email(
                    "test content",
                    "test subject",
                    "doesnotexist@igorville.com",
                    context={"domain_request": self},
                    bcc_address=None,
                )

        # Assert that an email wasn't sent
        self.assertFalse(self.mock_client.send_email.called)


class SendExpirationEmailsTests(TestCase):
    def setUp(self):
        # Hard set the date
        self.fixed_today = date(2025, 5, 29)
        # Create the users
        self.manager = User.objects.create(email="manager@example.com", username="manageruser")
        self.admin = User.objects.create(email="admin@example.com", username="adminuser")

    @patch("registrar.management.commands.send_expiring_soon_domains_notification.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_emails_sent_for_ready_domain_expiring_soon(self, mock_now, mock_send_email):
        """
        1. Email should send if domain is expiring soon in READY state
        2. Getting the right template
        3. Sending the correct context to the right people
        """
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        # Set up domain and portfolio and domain manager and admin permissions
        domain_ready = Domain.objects.create(
            name="readyexpiringsoon.gov",
            state=Domain.State.READY,
            expiration_date=self.fixed_today + timedelta(days=30),
        )
        portfolio = Portfolio.objects.create(requester=self.admin, organization_name="Expiring Soon")
        DomainInformation.objects.create(domain=domain_ready, portfolio=portfolio, requester=self.manager)

        UserDomainRole.objects.create(user=self.manager, domain=domain_ready, role="manager")

        UserPortfolioPermission.objects.create(
            user=self.manager,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=self.admin,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        call_command("send_expiring_soon_domains_notification")

        expected_context = {
            "domain": domain_ready,
            "days_remaining": 30,
            "expiration_date": self.fixed_today + timedelta(days=30),
        }

        mock_send_email.assert_any_call(
            "emails/ready_and_expiring_soon.txt",
            "emails/ready_and_expiring_soon_subject.txt",
            to_addresses=["manager@example.com"],
            cc_addresses=["admin@example.com"],
            context=expected_context,
        )

    @patch("registrar.management.commands.send_expiring_soon_domains_notification.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_emails_sent_for_dns_domain_expiring_soon(self, mock_now, mock_send_email):
        """
        1. Email should send if domain is expiring soon in DNS NEEDED state
        2. Getting the right template
        3. Sending the correct context to the right people (domain manager, org admin)
        """
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        domain_dns = Domain.objects.create(
            name="dnsexpiringsoon.gov",
            state=Domain.State.DNS_NEEDED,
            expiration_date=self.fixed_today + timedelta(days=7),
        )
        portfolio = Portfolio.objects.create(requester=self.admin, organization_name="Expiring Soon")
        DomainInformation.objects.create(domain=domain_dns, portfolio=portfolio, requester=self.manager)

        UserDomainRole.objects.create(user=self.manager, domain=domain_dns, role="manager")

        UserPortfolioPermission.objects.create(
            user=self.manager,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=self.admin,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        call_command("send_expiring_soon_domains_notification")

        expected_context = {
            "domain": domain_dns,
            "days_remaining": 7,
            "expiration_date": self.fixed_today + timedelta(days=7),
        }

        mock_send_email.assert_any_call(
            "emails/dns_needed_or_unknown_expiring_soon.txt",
            "emails/dns_needed_or_unknown_expiring_soon_subject.txt",
            to_addresses=["manager@example.com"],
            cc_addresses=["admin@example.com"],
            context=expected_context,
        )

    @patch("registrar.management.commands.send_expiring_soon_domains_notification.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_emails_sent_for_unknown_domain_expiring_soon(self, mock_now, mock_send_email):
        """
        1. Email should send if domain is expiring soon in UNKNOWN state
        2. Getting the right template
        3. Sending the correct context to the right people (domain manager, org admin)
        """
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        domain_unknown = Domain.objects.create(
            name="unknownexpiringsoon.gov",
            state=Domain.State.UNKNOWN,
            expiration_date=self.fixed_today + timedelta(days=7),
        )
        portfolio = Portfolio.objects.create(requester=self.admin, organization_name="Expiring Soon")
        DomainInformation.objects.create(domain=domain_unknown, portfolio=portfolio, requester=self.manager)

        UserDomainRole.objects.create(user=self.manager, domain=domain_unknown, role="manager")

        UserPortfolioPermission.objects.create(
            user=self.manager,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=self.admin,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        call_command("send_expiring_soon_domains_notification")

        expected_context = {
            "domain": domain_unknown,
            "days_remaining": 7,
            "expiration_date": self.fixed_today + timedelta(days=7),
        }

        mock_send_email.assert_any_call(
            "emails/dns_needed_or_unknown_expiring_soon.txt",
            "emails/dns_needed_or_unknown_expiring_soon_subject.txt",
            to_addresses=["manager@example.com"],
            cc_addresses=["admin@example.com"],
            context=expected_context,
        )

    @patch("registrar.management.commands.send_expiring_soon_domains_notification.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_no_emails_for_unrelated_domain_states(self, mock_now, mock_send_email):
        """
        1. Email should NOT send if it is expiring soon
        but NOT in ready/unknown/dns needed state
        """
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        # Domain is ONHOLD but still expiring soon
        _ = Domain.objects.create(
            name="pendingdomain.gov",
            state=Domain.State.ON_HOLD,
            expiration_date=self.fixed_today + timedelta(days=30),
        )
        call_command("send_expiring_soon_domains_notification")

        mock_send_email.assert_not_called()

    @patch("registrar.management.commands.send_expiring_soon_domains_notification.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_domains_expiring_later_do_not_trigger_email(self, mock_now, mock_send_email):
        """
        1. Email should NOT send as it's more than in the 30/7/1 days
        (domain is expiring soon in 60 days but we dont send a notification)
        """
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        # Create a domain expiring 60 days from fixed_today (more than 30/7/1 days)
        Domain.objects.create(
            name="laterexpiring.gov",
            state=Domain.State.READY,
            expiration_date=self.fixed_today + timedelta(days=60),
        )

        call_command("send_expiring_soon_domains_notification")

        mock_send_email.assert_not_called()

    @patch("registrar.management.commands.send_expiring_soon_domains_notification.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_expired_domains_do_not_trigger_email(self, mock_now, mock_send_email):
        """
        1. Email should NOT send bc domain is already expired
        """
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        # Create an expired domain (expired yesterday)
        expired_domain = Domain.objects.create(
            name="expireddomain.gov",
            state=Domain.State.READY,
            expiration_date=self.fixed_today - timedelta(days=1),
        )

        portfolio = Portfolio.objects.create(requester=self.admin, organization_name="Expired Domains Portfolio")

        DomainInformation.objects.create(
            domain=expired_domain,
            portfolio=portfolio,
            requester=self.manager,
        )

        UserDomainRole.objects.create(user=self.manager, domain=expired_domain, role="manager")

        UserPortfolioPermission.objects.create(
            user=self.manager,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=self.admin,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        call_command("send_expiring_soon_domains_notification")

        mock_send_email.assert_not_called()


class SendDomainSetupReminderTests(TestCase):
    def setUp(self):
        # Hard set the date
        self.fixed_today = date(2025, 5, 29)
        # Create the users
        self.manager = User.objects.create(email="manager@example.com", username="manageruser")
        self.admin = User.objects.create(email="admin@example.com", username="adminuser")

    @patch("registrar.management.commands.send_domain_setup_reminder.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_emails_sent_for_unknown_domain_7_days_after_approval(self, mock_now, mock_send_email):
        """
        1. Email should send if domain is in UNKNOWN state 7 days after approval
        2. Getting the right template
        3. Sending the correct context to the right people (domain manager, org admin)
        """
        # Set today to 7 days after domain creation
        seven_days_ago = self.fixed_today - timedelta(days=7)
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        domain_unknown = Domain.objects.create(
            name="unknownsetup.gov",
            state=Domain.State.UNKNOWN,
        )
        domain_unknown.created_at = timezone.make_aware(datetime.combine(seven_days_ago, datetime.min.time()))
        domain_unknown.save(update_fields=['created_at'])
        portfolio = Portfolio.objects.create(requester=self.admin, organization_name="Setup Reminder")
        DomainInformation.objects.create(domain=domain_unknown, portfolio=portfolio, requester=self.manager)
        UserDomainRole.objects.create(user=self.manager, domain=domain_unknown, role="manager")

        UserPortfolioPermission.objects.create(
            user=self.manager,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=self.admin,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        call_command("send_domain_setup_reminder")

        expected_context = {
            "domain": domain_unknown,
            "approval_date": seven_days_ago,
        }

        mock_send_email.assert_any_call(
            "emails/domain_setup_reminder.txt",
            "emails/domain_setup_reminder_subject.txt",
            to_addresses=["manager@example.com"],
            cc_addresses=["admin@example.com"],
            context=expected_context,
        )

    @patch("registrar.management.commands.send_domain_setup_reminder.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_emails_sent_for_dns_needed_domain_7_days_after_approval(self, mock_now, mock_send_email):
        """
        1. Email should send if domain is in DNS_NEEDED state 7 days after approval
        2. Getting the right template
        3. Sending the correct context to the right people (domain manager, org admin)
        """
        # Set today to 7 days after domain creation
        seven_days_ago = self.fixed_today - timedelta(days=7)
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        domain_dns = Domain.objects.create(
            name="dnssetup.gov",
            state=Domain.State.DNS_NEEDED,
        )
        domain_dns.created_at = timezone.make_aware(datetime.combine(seven_days_ago, datetime.min.time()))
        domain_dns.save(update_fields=['created_at'])
        portfolio = Portfolio.objects.create(requester=self.admin, organization_name="Setup Reminder")
        DomainInformation.objects.create(domain=domain_dns, portfolio=portfolio, requester=self.manager)
        UserDomainRole.objects.create(user=self.manager, domain=domain_dns, role="manager")

        UserPortfolioPermission.objects.create(
            user=self.manager,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=self.admin,
            portfolio=portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        call_command("send_domain_setup_reminder")

        expected_context = {
            "domain": domain_dns,
            "approval_date": seven_days_ago,
        }

        mock_send_email.assert_any_call(
            "emails/domain_setup_reminder.txt",
            "emails/domain_setup_reminder_subject.txt",
            to_addresses=["manager@example.com"],
            cc_addresses=["admin@example.com"],
            context=expected_context,
        )

    @patch("registrar.management.commands.send_domain_setup_reminder.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_emails_sent_for_legacy_domain_without_portfolio(self, mock_now, mock_send_email):
        """
        1. Email should send for legacy domains (no portfolio) 7 days after approval
        2. Only domain managers should be on TO line, no CC
        """
        # Set today to 7 days after domain creation
        seven_days_ago = self.fixed_today - timedelta(days=7)
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        domain_legacy = Domain.objects.create(
            name="legacysetup.gov",
            state=Domain.State.UNKNOWN,
        )
        domain_legacy.created_at = timezone.make_aware(datetime.combine(seven_days_ago, datetime.min.time()))
        domain_legacy.save(update_fields=['created_at'])
        # Create domain_info without portfolio (legacy mode)
        DomainInformation.objects.create(domain=domain_legacy, requester=self.manager)
        UserDomainRole.objects.create(user=self.manager, domain=domain_legacy, role="manager")

        call_command("send_domain_setup_reminder")

        expected_context = {
            "domain": domain_legacy,
            "approval_date": seven_days_ago,
        }

        mock_send_email.assert_any_call(
            "emails/domain_setup_reminder.txt",
            "emails/domain_setup_reminder_subject.txt",
            to_addresses=["manager@example.com"],
            cc_addresses=[],
            context=expected_context,
        )

    @patch("registrar.management.commands.send_domain_setup_reminder.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_no_emails_for_ready_domain(self, mock_now, mock_send_email):
        """
        1. Email should NOT send if domain is in READY state (already set up)
        """
        seven_days_ago = self.fixed_today - timedelta(days=7)
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        domain_ready = Domain.objects.create(
            name="readysetup.gov",
            state=Domain.State.READY,
            created_at=timezone.make_aware(datetime.combine(seven_days_ago, datetime.min.time())),
        )
        DomainInformation.objects.create(domain=domain_ready, requester=self.manager)
        UserDomainRole.objects.create(user=self.manager, domain=domain_ready, role="manager")

        call_command("send_domain_setup_reminder")

        mock_send_email.assert_not_called()

    @patch("registrar.management.commands.send_domain_setup_reminder.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_no_emails_for_domains_created_on_different_days(self, mock_now, mock_send_email):
        """
        1. Email should NOT send for domains created 6 or 8 days ago (only exactly 7 days)
        """
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        # Domain created 6 days ago
        six_days_ago = self.fixed_today - timedelta(days=6)
        domain_6_days = Domain.objects.create(
            name="sixdays.gov",
            state=Domain.State.UNKNOWN,
            created_at=timezone.make_aware(datetime.combine(six_days_ago, datetime.min.time())),
        )
        DomainInformation.objects.create(domain=domain_6_days, requester=self.manager)
        UserDomainRole.objects.create(user=self.manager, domain=domain_6_days, role="manager")

        # Domain created 8 days ago
        eight_days_ago = self.fixed_today - timedelta(days=8)
        domain_8_days = Domain.objects.create(
            name="eightdays.gov",
            state=Domain.State.UNKNOWN,
            created_at=timezone.make_aware(datetime.combine(eight_days_ago, datetime.min.time())),
        )
        DomainInformation.objects.create(domain=domain_8_days, requester=self.manager)
        UserDomainRole.objects.create(user=self.manager, domain=domain_8_days, role="manager")

        call_command("send_domain_setup_reminder")

        mock_send_email.assert_not_called()

    @patch("registrar.management.commands.send_domain_setup_reminder.send_templated_email")
    @patch("django.utils.timezone.now")
    def test_no_emails_for_domains_without_managers(self, mock_now, mock_send_email):
        """
        1. Email should NOT send if domain has no domain managers
        """
        seven_days_ago = self.fixed_today - timedelta(days=7)
        mock_now.return_value = timezone.make_aware(datetime.combine(self.fixed_today, datetime.min.time()))

        domain_no_manager = Domain.objects.create(
            name="nomanager.gov",
            state=Domain.State.UNKNOWN,
            created_at=timezone.make_aware(datetime.combine(seven_days_ago, datetime.min.time())),
        )
        DomainInformation.objects.create(domain=domain_no_manager, requester=self.manager)

        call_command("send_domain_setup_reminder")

        mock_send_email.assert_not_called()
