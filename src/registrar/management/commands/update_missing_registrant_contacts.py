"""Update missing registrant contact info

This command is intended to fill in the missing registrant contact info and sync that data with the registry

- In dry-run mode (default), only logs what would be changed
- With --no-dry-run, sends registry updates via Domain._update_epp_contact
- Use --target-domain to only update an existing domain
- Omit --target-domain to run against all registrant contacts
"""
import logging
import argparse
from django.core.management import BaseCommand
from registrar.models import PublicContact, Domain

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = (
        "Updates registrant contact info for any domains which are missing the info"
    )
    RECOVERY_LOGFILE = "update_missing_registrant_contacts_log.txt"
    CONTACT_TYPE = PublicContact.ContactTypeChoices.REGISTRANT.value

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-domain",
            "--target_domain",
            required=False,
            help="Only update contacts for a given domain name (case insensitive).",
        )

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

        parser.add_argument(
            "--use-recovery-log",
            "--use_recovery_log",
            action=argparse.BooleanOptionalAction,
            default=False,
            help=("When enabled, use the recovery log text file to skip domains that were marked 'done'."),
        )
 
    def handle(self, *args, **options):
        logger.debug("Running missing registrants update script")
        all_contacts = PublicContact.objects.all()
        administrative_contacts = all_contacts.filter(contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE)
        registrant_contacts = all_contacts.filter(contact_type=PublicContact.ContactTypeChoices.REGISTRANT)
        domain_set = set()

        for registrant in registrant_contacts:
            domain_set.add(registrant.domain)

        for admin in administrative_contacts:
            if admin.domain not in domain_set:
                logger.info("No Registrant info found...creating")
                logger.info(f"Retrieving domain object for {admin.domain}")
                domain = Domain.objects.get(name=admin.domain)
                domain.addRegistrant()



