"""Load domain invitations for existing domains and their contacts."""


# NOTE:  Do we want to add userID to transition_domain? (user might have multiple emails??)
# NOTE:  How to determine of email has been sent??

import csv
import logging

from collections import defaultdict

from django.core.management import BaseCommand

from registrar.models import TransitionDomain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Load data for domains that are in transition 
    (populates transition_domain model objects)."""

    def add_arguments(self, parser):
        """Add our three filename arguments."""
        parser.add_argument(
            "domain_contacts_filename", help="Data file with domain contact information"
        )
        parser.add_argument(
            "contacts_filename",
            help="Data file with contact information",
        )
        parser.add_argument(
            "domain_statuses_filename", help="Data file with domain status information"
        )

        parser.add_argument("--sep", default="|", help="Delimiter character")

    def handle(
        self,
        domain_contacts_filename,
        contacts_filename,
        domain_statuses_filename,
        **options
    ):
        """Load the data files and create the DomainInvitations."""
        sep = options.get("sep")

        """
        # Create mapping of userId -> domain names
        # We open the domain file first and hold it in memory.
        # There are three contacts per domain, so there should be at
        # most 3*N different contacts here.
        contact_domains = defaultdict(list)  # each contact has a list of domains
        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_contacts_file:
            for row in csv.reader(domain_contacts_file, delimiter=sep):
                # fields are just domain, userid, role
                # lowercase the domain names now
                contact_domains[row[1]].append(row[0].lower())
        logger.info("Loaded domains for %d contacts", len(contact_domains))

        # STEP 1:  
        # Create mapping of domain name -> userId 
        domains_contact = defaultdict(list)  # each contact has a list of domains
        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_contacts_file:
            for row in csv.reader(domain_contacts_file, delimiter=sep):
                # fields are just domain, userid, role
                # lowercase the domain names now --NOTE: is there a reason why we do this??
                domainName = row[0].lower()
                userId = row[1]
                domains_contact[domainName].append(userId)
        logger.info("Loaded domains for %d contacts", len(domains_contact))
        """

        # STEP 1:
        # Create mapping of domain name -> status
        domain_status = defaultdict()  # NOTE: how to determine "most recent" status?
        logger.info("Reading domain statuses data file %s", domain_statuses_filename)
        with open(domain_statuses_filename, "r") as domain_statuses_file:
            for row in csv.reader(domain_statuses_file, delimiter=sep):
                domainName = row[0].lower()
                domainStatus = row[1]
                domain_status[domainName] = domainStatus
        logger.info("Loaded statuses for %d domains", len(domain_status))

        # STEP 2:
        # Create mapping of userId -> emails NOTE: is this one to many??
        user_emails = defaultdict(list)  # each contact has a list of e-mails
        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(contacts_filename, "r") as contacts_file:
            for row in csv.reader(contacts_file, delimiter=sep):
                userId = row[0]
                user_email = row[6]
                user_emails[userId].append(user_email)
        logger.info("Loaded emails for %d users", len(user_emails))

        # STEP 3:
        # TODO:  Need to add logic for conflicting domain status entries
        # (which should not exist, but might)
        # TODO: log statuses found that don't map to the ones we have (count occurences)

        to_create = []

        # keep track of statuses that don't match our available status values
        outlier_statuses = set

        # keep track of domains that have no known status
        domains_without_status = set

        # keep track of users that have no e-mails
        users_without_email = set

        # keep track of domains we UPDATED (instead of ones we added)
        total_updated_domain_entries = 0

        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_contacts_file:
            for row in csv.reader(domain_contacts_file, delimiter=sep):
                # fields are just domain, userid, role
                # lowercase the domain names
                domainName = row[0]
                userId = row[1]

                domainStatus = TransitionDomain.StatusChoices.CREATED
                userEmail = ""
                emailSent = False
                # TODO: how to know if e-mail was sent?

                if domainName not in domain_status:
                    # this domain has no status...default to "Create"
                    domains_without_status.add(domainName)
                else:
                    originalStatus = domain_status[domainName]
                    if originalStatus in TransitionDomain.StatusChoices.values:
                        domainStatus = originalStatus
                    else:
                        # default all other statuses to "Create"
                        outlier_statuses.add(originalStatus)

                if userId not in user_emails:
                    # this user has no e-mail...this should never happen
                    users_without_email.add(userId)
                    break

                # Check to see if this domain-user pairing already exists so we don't add duplicates
                existingEntry = TransitionDomain.objects.get(
                    username=userEmail, domain_name=domainName
                )
                if existingEntry:
                    existingEntry.status = domainStatus
                    total_updated_domain_entries += 1
                else:
                    to_create.append(
                        TransitionDomain(
                            username=userEmail,
                            domain_name=domainName,
                            status=domainStatus,
                            email_sent=emailSent,
                        )
                    )
        logger.info("Creating %d transition domain entries", len(to_create))
        TransitionDomain.objects.bulk_create(to_create)

        logger.info(
            """Created %d transition domain entries, 
            updated %d transition domain entries,
            found %d users without email,
            found %d unique statuses that do not map to existing status values""",
            len(to_create),
            total_updated_domain_entries,
            len(users_without_email),
            len(outlier_statuses),
        )
        # TODO: add more info to logger?
