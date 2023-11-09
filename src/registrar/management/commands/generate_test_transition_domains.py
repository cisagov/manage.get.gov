"""Data migration: Generate fake transition domains, replacing existing ones."""

import logging

from django.core.management import BaseCommand
from registrar.models import TransitionDomain, Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate test transition domains from existing domains"

    # Generates test transition domains for testing send_domain_invitations script.
    # Running this script removes all existing transition domains, so use with caution.
    # Transition domains are created with email addresses provided as command line
    # argument. Email addresses for testing are passed as comma delimited list of
    # email addresses, and are required to be provided. Email addresses from the list
    # are assigned to transition domains at time of creation.

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "-e",
            "--emails",
            required=True,
            dest="emails",
            help="Comma-delimited list of email addresses to be used for testing",
        )

    def handle(self, **options):
        """Delete existing TransitionDomains.  Generate test ones.
        expects options[emails]; emails will be assigned to transition
        domains at the time of creation"""

        # split options[emails] into an array of test emails
        test_emails = options["emails"].split(",")

        if len(test_emails) > 0:
            # set up test data
            self.delete_test_transition_domains()
            self.load_test_transition_domains(test_emails)
        else:
            logger.error("list of emails for testing is required")

    def load_test_transition_domains(self, test_emails: list):
        """Load test transition domains"""

        # counter for test_emails index
        test_emails_counter = 0
        # Need to get actual domain names from the database for this test
        real_domains = Domain.objects.all()
        for real_domain in real_domains:
            TransitionDomain.objects.create(
                username=test_emails[test_emails_counter % len(test_emails)],
                domain_name=real_domain.name,
                status="created",
                email_sent=False,
            )
            test_emails_counter += 1

    def delete_test_transition_domains(self):
        self.transition_domains = TransitionDomain.objects.all()
        for transition_domain in self.transition_domains:
            transition_domain.delete()
