"""Test our email templates and sending."""

from unittest.mock import MagicMock

from django.test import TestCase, override_settings
from waffle.testutils import override_flag
from registrar.utility import email
from registrar.utility.email import send_templated_email
from .common import completed_domain_request
from registrar.models import AllowedEmail, User

from api.tests.common import less_console_noise_decorator
from datetime import datetime
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

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
            phone="(888) 888 8888",
            email="testy@town.com",
        )

        # Create a fake domain request
        domain_request = completed_domain_request(has_other_contacts=True, user=_creator)
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
    def test_email_whitelist(self):
        """Tests the email whitelist is enabled elsewhere"""
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            expected_message = "Could not send email. "
            "The email 'doesnotexist@igorville.com' does not exist within the whitelist."
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
