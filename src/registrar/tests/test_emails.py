"""Test our email templates and sending."""

from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from registrar.models import Contact, Domain, Website, DomainApplication

import boto3_mocking  # type: ignore


class TestEmails(TestCase):
    def _completed_application(self):
        """A completed domain application."""
        user = get_user_model().objects.create(username="username")
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(555) 555 5555",
        )
        domain, _ = Domain.objects.get_or_create(name="city.gov")
        alt, _ = Website.objects.get_or_create(website="city1.gov")
        current, _ = Website.objects.get_or_create(website="city.com")
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
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            requested_domain=domain,
            submitter=you,
            creator=user,
        )
        application.other_contacts.add(other)
        application.current_websites.add(current)
        application.alternative_domains.add(alt)

        return application

    @boto3_mocking.patching
    def test_submission_confirmation(self):
        """Submission confirmation email works."""
        application = self._completed_application()

        mock_client_class = MagicMock()
        mock_client = mock_client_class.return_value
        with boto3_mocking.clients.handler_for("sesv2", mock_client_class):
            application.submit()

        # check that an email was sent
        self.assertTrue(mock_client.send_email.called)

        # check the call sequence for the email
        args, kwargs = mock_client.send_email.call_args
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
        self.assertIn("Current website for your organization:", body)
        self.assertIn("city.com", body)
        self.assertNotIn("Type of work:", body)
