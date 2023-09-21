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

        debug_MaxEntriesToParse = 10

        class termColors:
            HEADER = '\033[95m'
            OKBLUE = '\033[94m'
            OKCYAN = '\033[96m'
            OKGREEN = '\033[92m'
            WARNING = '\033[93m'
            FAIL = '\033[91m'
            ENDC = '\033[0m'
            BOLD = '\033[1m'
            UNDERLINE = '\033[4m'
        if __debug__:
            print(termColors.WARNING)
            print("----------DEBUG MODE ON----------")
            print(f"Parsing of entries will be limited to {debug_MaxEntriesToParse} lines per file.")
            print("Detailed print statements activated.")
            print(termColors.ENDC)

        # STEP 1:
        # Create mapping of domain name -> status
        # TODO: figure out latest status
        domain_status_dictionary = defaultdict(str)  # NOTE: how to determine "most recent" status?
        logger.info("Reading domain statuses data file %s", domain_statuses_filename)
        with open(domain_statuses_filename, "r") as domain_statuses_file:
            for row in csv.reader(domain_statuses_file, delimiter=sep):
                domainName = row[0].lower()
                domainStatus = row[1].lower()
                # print("adding "+domainName+", "+domainStatus)
                domain_status_dictionary[domainName] = domainStatus
        logger.info("Loaded statuses for %d domains", len(domain_status_dictionary))

        # STEP 2:
        # Create mapping of userId -> emails NOTE: is this one to many??
        user_emails_dictionary = defaultdict(list)  # each contact has a list of e-mails
        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(contacts_filename, "r") as contacts_file:
            for row in csv.reader(contacts_file, delimiter=sep):
                userId = row[0]
                user_email = row[6]
                user_emails_dictionary[userId].append(user_email)
        logger.info("Loaded emails for %d users", len(user_emails_dictionary))

        # STEP 3:
        # TODO:  Need to add logic for conflicting domain status entries
        # (which should not exist, but might)
        # TODO: log statuses found that don't map to the ones we have (count occurences)

        to_create = []

        # keep track of statuses that don't match our available status values
        outlier_statuses = set
        total_outlier_statuses = 0

        # keep track of domains that have no known status
        domains_without_status = set
        total_domains_without_status = 0

        # keep track of users that have no e-mails
        users_without_email = set
        total_users_without_email = 0

        # keep track of domains we UPDATED (instead of ones we added)
        total_updated_domain_entries = 0
        total_new_entries = 0

        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_contacts_file:
            for row in csv.reader(domain_contacts_file, delimiter=sep):
                # fields are just domain, userid, role
                # lowercase the domain names
                domainName = row[0].lower()
                userId = row[1]

                domainStatus = TransitionDomain.StatusChoices.CREATED
                userEmail = ""
                emailSent = False
                # TODO: how to know if e-mail was sent?

                if domainName not in domain_status_dictionary:
                    # this domain has no status...default to "Create"
                    # domains_without_status.add(domainName)
                    # print("No status found for domain: "+domainName)
                    total_domains_without_status += 1
                else:
                    originalStatus = domain_status_dictionary[domainName]
                    # print(originalStatus)
                    if originalStatus in TransitionDomain.StatusChoices.values:
                        # print("YAY")
                        domainStatus = originalStatus
                    else:
                        # default all other statuses to "Create"
                        # outlier_statuses.add(originalStatus)
                        # print("Unknown status: "+originalStatus)
                        total_outlier_statuses += 1

                if userId not in user_emails_dictionary:
                    # this user has no e-mail...this should never happen
                    # users_without_email.add(userId)
                    # print("no e-mail found for user: "+userId)
                    total_users_without_email += 1
                else:
                    userEmail = user_emails_dictionary[userId]

                # Check to see if this domain-user pairing already exists so we don't add duplicates
                '''
                newOrExistingEntry, isNew = TransitionDomain.objects.get_or_create(
                    username=userEmail, 
                    domain_name=domainName
                )
                if isNew:
                    total_updated_domain_entries += 1
                else:
                    total_new_entries += 1
                newOrExistingEntry.status = domainStatus
                newOrExistingEntry.email_sent = emailSent
                to_create.append(
                    newOrExistingEntry
                )
                '''

                try:
                    existingEntry = TransitionDomain.objects.get(
                    username=userEmail, 
                    domain_name=domainName
                    )

                    # DEBUG:
                    if __debug__:
                        print(termColors.WARNING)
                        print("Updating entry: ", existingEntry)
                        print("     Status: ", existingEntry.status, " > ",domainStatus)
                        print("     Email Sent: ", existingEntry.email_sent, " > ", emailSent)

                    existingEntry.status = domainStatus
                    existingEntry.email_sent = emailSent
                    existingEntry.save()
                except TransitionDomain.DoesNotExist:
                    # no matching entry, make one
                    newEntry = TransitionDomain(
                        username=userEmail, 
                        domain_name=domainName,
                        status = domainStatus,
                        email_sent = emailSent
                    )
                    to_create.append(newEntry)

                    # DEBUG:
                    if __debug__:
                        print("Adding entry ",total_new_entries,": ", newEntry)
                    
                total_new_entries += 1
                
                # DEBUG:
                if __debug__:
                    if total_new_entries > debug_MaxEntriesToParse:
                        print("----BREAK----")
                        print(termColors.ENDC)
                        break

        logger.info("Creating %d transition domain entries", len(to_create))
        TransitionDomain.objects.bulk_create(to_create)

        logger.info(
            """Created %d transition domain entries, 
            updated %d transition domain entries,
            found %d users without email,
            found %d unique statuses that do not map to existing status values""",
            total_new_entries,
            total_updated_domain_entries,
            total_users_without_email,
            total_outlier_statuses,
        )
        # TODO: add more info to logger?
