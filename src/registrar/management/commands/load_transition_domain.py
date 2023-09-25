"""Load domain invitations for existing domains and their contacts."""


# NOTE:  Do we want to add userID to transition_domain?
# (user might have multiple emails??)
# NOTE:  How to determine of email has been sent??

import csv
import logging
import argparse

from collections import defaultdict

from django.core.management import BaseCommand

from registrar.models import TransitionDomain

logger = logging.getLogger(__name__)


class termColors:
    """Colors for terminal outputs
    (makes reading the logs WAY easier)"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BackgroundLightYellow = "\033[103m"


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        logger.info(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            logger.info("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


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

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse", default=0, help="Sets max number of entries to load"
        )

        parser.add_argument(
            "--resetTable",
            help="Deletes all data in the TransitionDomain table",
            action=argparse.BooleanOptionalAction,
        )

    def handle(
        self,
        domain_contacts_filename,
        contacts_filename,
        domain_statuses_filename,
        **options,
    ):
        """Load the data files and create the DomainInvitations."""
        sep = options.get("sep")

        if options.get("resetTable"):
            confirmReset = query_yes_no(
                f"""
            {termColors.FAIL}
            WARNING: Resetting the table will permanently delete all the data!  
            Are you sure you want to continue?{termColors.ENDC}"""
            )
            if confirmReset:
                logger.info(
                f"""{termColors.WARNING}
                ----------Clearing Table Data----------
                (please wait)
                {termColors.ENDC}"""
                )
                TransitionDomain.objects.all().delete()

        debugOn = options.get("debug")
        debug_MaxEntriesToParse = int(
            options.get("limitParse")
        )  # set to 0 to parse all entries

        if debugOn:
            logger.info(
            f"""{termColors.OKCYAN}
            ----------DEBUG MODE ON----------
            Detailed print statements activated.
            {termColors.ENDC}
            """
            )
        if debug_MaxEntriesToParse > 0:
            logger.info(
            f"""{termColors.OKCYAN}
            ----------LIMITER ON----------
            Parsing of entries will be limited to {debug_MaxEntriesToParse} lines per file.")
            Detailed print statements activated.
            {termColors.ENDC}
            """
            )

        # STEP 1:
        # Create mapping of domain name -> status
        # TODO: figure out latest status
        domain_status_dictionary = defaultdict(
            str
        )  # NOTE: how to determine "most recent" status?
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
        outlier_statuses = []
        total_outlier_statuses = 0

        # keep track of domains that have no known status
        domains_without_status = []
        total_domains_without_status = 0

        # keep track of users that have no e-mails
        users_without_email = []
        total_users_without_email = 0

        # keep track of dupliucations..
        duplicate_domains = []
        duplicate_domain_user_combos = []

        # keep track of domains we UPDATED (instead of ones we added)
        total_updated_domain_entries = 0

        total_new_entries = 0
        total_rows_parsed = 0

        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_contacts_file:
            for row in csv.reader(domain_contacts_file, delimiter=sep):
                total_rows_parsed += 1

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
                    if domainName not in domains_without_status:
                        domains_without_status.append(domainName)
                    total_domains_without_status += 1
                else:
                    originalStatus = domain_status_dictionary[domainName]
                    # print(originalStatus)
                    if originalStatus in TransitionDomain.StatusChoices.values:
                        # This status maps directly to our available status options
                        domainStatus = originalStatus
                    else:
                        # Map all other status as follows;
                        # "serverHold” fields will map to hold clientHold to hold
                        # and any ok state should map to Ready.
                        # Check if there are any statuses that are not
                        # serverhold, client hold or OK in the original data set.
                        if (
                            originalStatus.lower() == "serverhold"
                            or originalStatus.lower() == "clienthold"
                        ):
                            domainStatus = TransitionDomain.StatusChoices.HOLD
                        elif originalStatus.lower() != "ok":
                            if originalStatus not in outlier_statuses:
                                outlier_statuses.append(originalStatus)
                            logger.info("Unknown status: " + originalStatus)
                            total_outlier_statuses += 1

                if userId not in user_emails_dictionary:
                    # this user has no e-mail...this should never happen
                    # users_without_email.add(userId)
                    # print("no e-mail found for user: "+userId)
                    total_users_without_email += 1
                else:
                    userEmail = user_emails_dictionary[userId]

                # Check for duplicate data in the file we are parsing so we do not add duplicates
                # NOTE: Currently, we allow duplicate domains, but not duplicate domain-user pairs.
                # However, track duplicate domains for now, since we are still deciding on whether
                # to make this field unique or not. ~10/25/2023
                tempEntry_domain = next(
                    (x for x in to_create if x.domain_name == domainName), None
                )
                tempEntry_domainUserPair = next(
                    (
                        x
                        for x in to_create
                        if x.username == userEmail and x.domain_name == domainName
                    ),
                    None,
                )
                if tempEntry_domain is not None:
                    if debugOn:
                        logger.info(
                        f"{termColors.WARNING} DUPLICATE Verisign entries found for domain: {domainName} {termColors.ENDC}"
                        )
                    if domainName not in duplicate_domains:
                        duplicate_domains.append(domainName)
                if tempEntry_domainUserPair != None:
                    if debugOn:
                        logger.info(
                        f"""
{termColors.WARNING} 
DUPLICATE Verisign entries found for domain - user {termColors.BackgroundLightYellow} PAIR {termColors.ENDC}{termColors.WARNING}: 
{domainName} - {user_email} {termColors.ENDC}"""
                        )
                    if tempEntry_domainUserPair not in duplicate_domain_user_combos:
                        duplicate_domain_user_combos.append(tempEntry_domainUserPair)
                else:
                    try:
                        existingEntry = TransitionDomain.objects.get(
                            username=userEmail, domain_name=domainName
                        )

                        if existingEntry.status != domainStatus:
                            # DEBUG:
                            if debugOn:
                                logger.info(
                                    f"""{termColors.OKCYAN} 
                                    Updating entry: {existingEntry}
                                    Status: {existingEntry.status} > {domainStatus}
                                    Email Sent: {existingEntry.email_sent} > {emailSent}
                                    {termColors.ENDC}"""
                                )

                            existingEntry.status = domainStatus

                        existingEntry.email_sent = emailSent
                        existingEntry.save()
                    except TransitionDomain.DoesNotExist:
                        # no matching entry, make one
                        newEntry = TransitionDomain(
                            username=userEmail,
                            domain_name=domainName,
                            status=domainStatus,
                            email_sent=emailSent,
                        )
                        to_create.append(newEntry)
                        total_new_entries += 1

                        # DEBUG:
                        if debugOn:
                            logger.info(
                            f"{termColors.OKCYAN} Adding entry {total_new_entries}: {newEntry} {termColors.ENDC}"
                            )
                    except TransitionDomain.MultipleObjectsReturned:
                        logger.info(
                            f"""
{termColors.FAIL}
!!! ERROR: duplicate entries exist in the transtion_domain table for domain: {domainName}
----------TERMINATING----------"""
                        )
                        import sys

                        sys.exit()

                # DEBUG:
                if debugOn or debug_MaxEntriesToParse > 0:
                    if (
                        total_rows_parsed > debug_MaxEntriesToParse
                        and debug_MaxEntriesToParse != 0
                    ):
                        logger.info(
                            f"""{termColors.WARNING}
                            ----BREAK----
                            {termColors.ENDC}
                            """
                        )
                        break

        TransitionDomain.objects.bulk_create(to_create)

        logger.info(
            f"""{termColors.OKGREEN}

        ============= FINISHED ===============
        Created {total_new_entries} transition domain entries, 
        updated {total_updated_domain_entries} transition domain entries
        {termColors.ENDC}
        """
        )

        # Print a summary of findings (duplicate entries, missing data..etc.)
        totalDupDomainUserPairs = len(duplicate_domain_user_combos)
        totalDupDomains = len(duplicate_domains)
        if total_users_without_email > 0:
            logger.warning(
                "No e-mails found for users: {}".format(
                    ", ".join(map(str, users_without_email))
                )
            )
        if totalDupDomainUserPairs > 0 or totalDupDomains > 0:
            temp_dupPairsAsString = "{}".format(
                ", ".join(map(str, duplicate_domain_user_combos))
            )
            temp_dupDomainsAsString = "{}".format(
                ", ".join(map(str, duplicate_domains))
            )
            logger.warning(
                f"""{termColors.WARNING}
                            
                ----DUPLICATES FOUND-----

                {totalDupDomainUserPairs} DOMAIN - USER pairs were NOT unique in the supplied data files;

                {temp_dupPairsAsString}

                {totalDupDomains} DOMAINS were NOT unique in the supplied data files;

                {temp_dupDomainsAsString}
                {termColors.ENDC}"""
            )
        if total_domains_without_status > 0:
            temp_arrayToString = "{}".format(
                ", ".join(map(str, domains_without_status))
            )
            logger.warning(
                f"""{termColors.WARNING}
                           
            ----Found {total_domains_without_status} domains without a status (defaulted to READY)-----

            {temp_arrayToString}
            {termColors.ENDC}"""
            )

        if total_outlier_statuses > 0:
            temp_arrayToString = "{}".format(", ".join(map(str, outlier_statuses)))
            logger.warning(
                f"""{termColors.WARNING}
                           
            ----Found {total_outlier_statuses} unaccounted for statuses-----

            No mappings found for the following statuses (defaulted to Ready): 
            
            {temp_arrayToString}
            {termColors.ENDC}"""
            )
