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
        #Get all contacts
        all_contacts = PublicContact.objects.all()
        #Filter out just the administrative contacts
        administrative_contacts = all_contacts.filter(contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE)
        #Filter out the existing registrant contacts
        registrant_contacts = all_contacts.filter(contact_type=PublicContact.ContactTypeChoices.REGISTRANT)
        
        registratnt_domain_set = set()

        #Add all domains with registrant contacts to the set
        for registrant in registrant_contacts:
            registratnt_domain_set.add(registrant.domain)
        
        #Loop thru the administrative contacts
        for contact in administrative_contacts:
            #If the contact domain is not part of the registrant domain set, then create a new registrant contact
            if contact.domain not in registratnt_domain_set:
                logger.info("No Registrant info found...creating")
                logger.info(f"Retrieving domain object for {contact.domain}")
                #Get the domain object so we can call the addRegistrant method
                domain = Domain.objects.get(name=contact.domain)
                #Add the registrant
                domain.addRegistrant()



