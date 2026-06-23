"""Update missing registrant contact info

This command is intended to fill in the missing registrant contact info and sync that data with the registry

- In dry-run mode (default), only logs what would be changed
- With --no-dry-run, sends registry updates via Domain.addRegistrant()
"""

import logging
import argparse
from django.core.management import BaseCommand
from registrar.models import PublicContact, Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Updates registrant contact info for any domains which are missing the info"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "When enabled (which is the default), does not call the registry; only reports what would be updated. "
                "Disable with --no-dry-run to perform updates."
            ),
        )

    def handle(self, *args, **options):
        logger.debug("Running missing registrants update script")
        dry_run = bool(options.get("dry_run", True))
        # Get all contacts
        all_contacts = PublicContact.objects.all()
        # Get all domains
        all_domains = Domain.objects.all()
        # Filter out the existing registrant contacts
        registrant_contacts = all_contacts.filter(contact_type=PublicContact.ContactTypeChoices.REGISTRANT)

        registrant_domain_set = set()

        # Add all domains with registrant contacts to the set
        for registrant in registrant_contacts:
            registrant_domain_set.add(registrant.domain.name)

        # If the counts match up, every domain has a registrant contact
        if all_domains.count() == len(registrant_domain_set):
            logger.info("No missing registrants found")
            return 0

        # Loop thru the domains
        for domain in all_domains:
            # If the domain is not part of the registrant domain set, then create a new registrant contact
            if domain.name not in registrant_domain_set:
                logger.info("No Registrant info found...creating")
                # If this is a dry run, just output the domain for tracking purposes
                if dry_run:
                    logger.info(f"Dry run enabled...skipping adding registrant for {domain.name}")
                # Add the registrant
                else:
                    logger.info(f"Creating Registrant Public Contact for {domain.name}")
                    try:
                        domain.addRegistrant()
                    except Exception as e:
                        logger.error(f"Error adding domain registrant {domain.name}: {e}")
                        
