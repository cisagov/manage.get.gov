"""Test our email templates and sending."""

from unittest.mock import MagicMock

from django.test import TestCase
from .common import completed_application, less_console_noise


import boto3_mocking  # type: ignore


class TestEmails(TestCase):
    def setUp(self):
        self.mock_client_class = MagicMock()
        self.mock_client = self.mock_client_class.return_value

    @boto3_mocking.patching
    def test_submission_confirmation(self):
        """Submission confirmation email works."""
        application = completed_application()

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()

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
        self.assertIn("Authorizing official:", body)
        self.assertIn("Testy Tester", body)
        self.assertIn(".gov domain:", body)
        self.assertIn("city.gov", body)
        self.assertIn("city1.gov", body)

        # check for optional things
        self.assertIn("Other employees from your organization:", body)
        self.assertIn("Testy2 Tester2", body)
        self.assertIn("Current websites:", body)
        self.assertIn("city.com", body)
        self.assertIn("About your organization:", body)
        self.assertIn("Anything else", body)

    @boto3_mocking.patching
    def test_submission_confirmation_no_current_website_spacing(self):
        """Test line spacing without current_website."""
        application = completed_application(has_current_website=False)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("Current websites:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5555\n\n.gov domain:")

    @boto3_mocking.patching
    def test_submission_confirmation_current_website_spacing(self):
        """Test line spacing with current_website."""
        application = completed_application(has_current_website=True)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("Current websites:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5555\n\nCurrent websites:")
        self.assertRegex(body, r"city.com\n\n.gov domain:")

    @boto3_mocking.patching
    def test_submission_confirmation_other_contacts_spacing(self):
        """Test line spacing with other contacts."""
        application = completed_application(has_other_contacts=True)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("Other employees from your organization:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5556\n\nOther employees")
        self.assertRegex(body, r"5557\n\nAnything else")

    @boto3_mocking.patching
    def test_submission_confirmation_no_other_contacts_spacing(self):
        """Test line spacing without other contacts."""
        application = completed_application(has_other_contacts=False)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("Other employees from your organization:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5556\n\nAnything else")

    @boto3_mocking.patching
    def test_submission_confirmation_alternative_govdomain_spacing(self):
        """Test line spacing with alternative .gov domain."""
        application = completed_application(has_alternative_gov_domain=True)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("city1.gov", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"city.gov\ncity1.gov\n\nPurpose of your domain:")

    @boto3_mocking.patching
    def test_submission_confirmation_no_alternative_govdomain_spacing(self):
        """Test line spacing without alternative .gov domain."""
        application = completed_application(has_alternative_gov_domain=False)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("city1.gov", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"city.gov\n\nPurpose of your domain:")

    @boto3_mocking.patching
    def test_submission_confirmation_about_your_organization_spacing(self):
        """Test line spacing with about your organization."""
        application = completed_application(has_about_your_organization=True)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("About your organization:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"10002\n\nAbout your organization:")

    @boto3_mocking.patching
    def test_submission_confirmation_no_about_your_organization_spacing(self):
        """Test line spacing without about your organization."""
        application = completed_application(has_about_your_organization=False)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("About your organization:", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"10002\n\nAuthorizing official:")

    @boto3_mocking.patching
    def test_submission_confirmation_anything_else_spacing(self):
        """Test line spacing with anything else."""
        application = completed_application(has_anything_else=True)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5557\n\nAnything else?")

    @boto3_mocking.patching
    def test_submission_confirmation_no_anything_else_spacing(self):
        """Test line spacing without anything else."""
        application = completed_application(has_anything_else=False)
        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            with less_console_noise():
                application.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertNotIn("Anything else", body)
        # spacing should be right between adjacent elements
        self.assertRegex(body, r"5557\n\n----")
