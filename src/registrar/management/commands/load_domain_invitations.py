"""Load domain invitations for existing domains and their contacts."""

import csv
import logging

from collections import defaultdict

from django.core.management import BaseCommand

from registrar.models import Domain, DomainInvitation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load invitations for existing domains and their users."

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument(
            "domain_contacts_filename",
            help="Data file with domain contact information",
        )
        parser.add_argument("contacts_filename", help="Data file with contact information")

        parser.add_argument("--sep", default="|", help="Delimiter character")

    def handle(self, domain_contacts_filename, contacts_filename, **options):
        """Load the data files and create the DomainInvitations."""
        sep = options.get("sep")

        # We open the domain file first and hold it in memory.
        # There are three contacts per domain, so there should be at
        # most 3*N different contacts here.
        contact_domains = defaultdict(list)  # each contact has a list of domains
        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_file:
            for row in csv.reader(domain_file, delimiter=sep):
                # fields are just domain, userid, role
                # lowercase the domain names now
                contact_domains[row[1]].append(row[0].lower())
        logger.info("Loaded domains for %d contacts", len(contact_domains))

        # now we have a mapping of user IDs to lists of domains for that user
        # iterate over the contacts list and for contacts in our mapping,
        # create the domain invitations for their email address
        logger.info("Reading contacts data file %s", contacts_filename)
        to_create = []
        skipped = 0
        with open(contacts_filename, "r") as contacts_file:
            for row in csv.reader(contacts_file, delimiter=sep):
                # userid is in the first field, email is the seventh
                userid = row[0]
                if userid not in contact_domains:
                    # this user has no domains, skip them
                    skipped += 1
                    continue
                for domain_name in contact_domains[userid]:
                    email_address = row[6]
                    domain = Domain.objects.get(name=domain_name)
                    to_create.append(
                        DomainInvitation(
                            email=email_address.lower(),
                            domain=domain,
                            status=DomainInvitation.DomainInvitationStatus.INVITED,
                        )
                    )
        logger.info("Creating %d invitations", len(to_create))
        DomainInvitation.objects.bulk_create(to_create)
        logger.info(
            "Created %d domain invitations, ignored %d contacts",
            len(to_create),
            skipped,
        )
