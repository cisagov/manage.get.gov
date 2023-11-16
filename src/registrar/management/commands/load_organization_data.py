"""Data migration: Send domain invitations once to existing customers."""

import argparse
import logging
import copy
import time

from django.core.management import BaseCommand
from registrar.management.commands.utility.extra_transition_domain_helper import OrganizationDataLoader
from registrar.management.commands.utility.transition_domain_arguments import TransitionDomainArguments
from registrar.models import TransitionDomain
from ...utility.email import send_templated_email, EmailSendingError
from typing import List

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send domain invitations once to existing customers."

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.add_argument("--sep", default="|", help="Delimiter character")

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument("--directory", default="migrationdata", help="Desired directory")

        parser.add_argument(
            "--domain_additional_filename",
            help="Defines the filename for additional domain data",
            required=True,
        )

        parser.add_argument(
            "--organization_adhoc_filename",
            help="Defines the filename for domain type adhocs",
            required=True,
        )

    def handle(self, **options):
        """Process the objects in TransitionDomain."""
        args = TransitionDomainArguments(**options)

        load = OrganizationDataLoader(args)
        load.update_organization_data_for_all()
