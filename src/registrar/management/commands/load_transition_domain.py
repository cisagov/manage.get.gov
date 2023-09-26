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

    def handle(  # noqa: C901
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
                WARNING: Resetting the table will permanently delete all
                the data!
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

        debug_on = options.get("debug")
        debug_max_entries_to_parse = int(
            options.get("limitParse")
        )  # set to 0 to parse all entries

        self.print_debug_mode_statements(debug_on, debug_max_entries_to_parse)

        # STEP 1:
        # Create mapping of domain name -> status
        domain_status_dictionary = self.get_domain_user_dict(
            domain_statuses_filename, sep
        )

        # STEP 2:
        # Create mapping of userId  -> email
        user_emails_dictionary = self.get_user_emails_dict(contacts_filename, sep)

        # STEP 3:
        # TODO:  Need to add logic for conflicting domain status
        # entries
        # (which should not exist, but might)
        # TODO: log statuses found that don't map to the ones
        # we have (count occurences)

        to_create = []

        # keep track of statuses that don't match our available
        # status values
        outlier_statuses = []

        # keep track of domains that have no known status
        domains_without_status = []

        # keep track of users that have no e-mails
        users_without_email = []

        # keep track of duplications..
        duplicate_domains = []
        duplicate_domain_user_combos = []

        # keep track of domains we ADD or UPDATE
        total_updated_domain_entries = 0
        total_new_entries = 0

        # if we are limiting our parse (for testing purposes, keep
        # track of total rows parsed)
        total_rows_parsed = 0

        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_contacts_file:
            for row in csv.reader(domain_contacts_file, delimiter=sep):
                total_rows_parsed += 1

                # fields are just domain, userid, role
                # lowercase the domain names
                new_entry_domainName = row[0].lower()
                userId = row[1]

                new_entry_status = TransitionDomain.StatusChoices.READY
                new_entry_email = ""
                new_entry_emailSent = False
                # TODO: how to know if e-mail was sent?

                if new_entry_domainName not in domain_status_dictionary:
                    # this domain has no status...default to "Create"
                    if new_entry_domainName not in domains_without_status:
                        domains_without_status.append(new_entry_domainName)
                else:
                    original_status = domain_status_dictionary[new_entry_domainName]
                    # print(originalStatus)
                    mapped_status = self.get_mapped_status(original_status)
                    if mapped_status is None:
                        logger.info("Unknown status: " + original_status)
                        outlier_statuses.append(original_status)
                    else:
                        new_entry_status = mapped_status

                if userId not in user_emails_dictionary:
                    # this user has no e-mail...this should never happen
                    if userId not in users_without_email:
                        users_without_email.append(userId)
                else:
                    new_entry_email = user_emails_dictionary[userId]

                # Check for duplicate data in the file we are
                # parsing so we do not add duplicates
                # NOTE: Currently, we allow duplicate domains,
                # but not duplicate domain-user pairs.
                # However, track duplicate domains for now,
                # since we are still deciding on whether
                # to make this field unique or not. ~10/25/2023
                tempEntry_domain = next(
                    (x for x in to_create if x.domain_name == new_entry_domainName),
                    None,
                )
                tempEntry_domainUserPair = next(
                    (
                        x
                        for x in to_create
                        if x.username == new_entry_email
                        and x.domain_name == new_entry_domainName
                    ),
                    None,
                )
                if tempEntry_domain is not None:
                    if debug_on:
                        logger.info(
                            f"{termColors.WARNING} DUPLICATE Verisign entries found for domain: {new_entry_domainName} {termColors.ENDC}"  # noqa
                        )
                    if new_entry_domainName not in duplicate_domains:
                        duplicate_domains.append(new_entry_domainName)
                if tempEntry_domainUserPair is not None:
                    if debug_on:
                        logger.info(
                            f"""{termColors.WARNING} DUPLICATE Verisign entries found for domain - user {termColors.BackgroundLightYellow} PAIR {termColors.ENDC}{termColors.WARNING}:  
                            {new_entry_domainName} - {new_entry_email} {termColors.ENDC}"""  # noqa
                        )
                    if tempEntry_domainUserPair not in duplicate_domain_user_combos:
                        duplicate_domain_user_combos.append(tempEntry_domainUserPair)
                else:
                    try:
                        existingEntry = TransitionDomain.objects.get(
                            username=new_entry_email, domain_name=new_entry_domainName
                        )

                        if existingEntry.status != new_entry_status:
                            # DEBUG:
                            if debug_on:
                                logger.info(
                                    f"""{termColors.OKCYAN}
    Updating entry: {existingEntry}
    Status: {existingEntry.status} > {new_entry_status}
    Email Sent: {existingEntry.email_sent} > {new_entry_emailSent}
    {termColors.ENDC}"""
                                )

                            existingEntry.status = new_entry_status

                        existingEntry.email_sent = new_entry_emailSent
                        existingEntry.save()
                    except TransitionDomain.DoesNotExist:
                        # no matching entry, make one
                        newEntry = TransitionDomain(
                            username=new_entry_email,
                            domain_name=new_entry_domainName,
                            status=new_entry_status,
                            email_sent=new_entry_emailSent,
                        )
                        to_create.append(newEntry)
                        total_new_entries += 1

                        # DEBUG:
                        if debug_on:
                            logger.info(
                                f"{termColors.OKCYAN} Adding entry {total_new_entries}: {newEntry} {termColors.ENDC}"  # noqa
                            )
                    except TransitionDomain.MultipleObjectsReturned:
                        logger.info(
                            f"""
{termColors.FAIL}
!!! ERROR: duplicate entries exist in the
transtion_domain table for domain:
{new_entry_domainName}
----------TERMINATING----------"""
                        )
                        import sys

                        sys.exit()

                # DEBUG:
                if debug_on or debug_max_entries_to_parse > 0:
                    if (
                        total_rows_parsed > debug_max_entries_to_parse
                        and debug_max_entries_to_parse != 0
                    ):
                        logger.info(
                            f"""{termColors.WARNING}
                            ----PARSE LIMIT REACHED.  HALTING PARSER.----
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

        # Print a summary of findings (duplicate entries,
        # missing data..etc.)
        self.print_summary_duplications(
            duplicate_domain_user_combos, duplicate_domains, users_without_email
        )
        self.print_summary_status_findings(domains_without_status, outlier_statuses)

    def print_debug_mode_statements(self, debug_on, debug_max_entries_to_parse):
        if debug_on:
            logger.info(
                f"""{termColors.OKCYAN}
            ----------DEBUG MODE ON----------
            Detailed print statements activated.
            {termColors.ENDC}
            """
            )
        if debug_max_entries_to_parse > 0:
            logger.info(
                f"""{termColors.OKCYAN}
            ----------LIMITER ON----------
            Parsing of entries will be limited to
            {debug_max_entries_to_parse} lines per file.")
            Detailed print statements activated.
            {termColors.ENDC}
            """
            )

    def get_domain_user_dict(self, domain_statuses_filename, sep):
        """Creates a mapping of domain name -> status"""
        # TODO: figure out latest status
        domain_status_dictionary = defaultdict(str)
        # NOTE: how to determine "most recent" status?
        logger.info("Reading domain statuses data file %s", domain_statuses_filename)
        with open(domain_statuses_filename, "r") as domain_statuses_file:  # noqa
            for row in csv.reader(domain_statuses_file, delimiter=sep):
                domainName = row[0].lower()
                domainStatus = row[1].lower()
                # print("adding "+domainName+", "+domainStatus)
                domain_status_dictionary[domainName] = domainStatus
        logger.info("Loaded statuses for %d domains", len(domain_status_dictionary))
        return domain_status_dictionary

    def get_user_emails_dict(self, contacts_filename, sep):
        """Creates mapping of userId -> emails"""
        # NOTE: is this one to many??
        user_emails_dictionary = defaultdict(list)
        logger.info("Reading domain-contacts data file %s", contacts_filename)
        with open(contacts_filename, "r") as contacts_file:
            for row in csv.reader(contacts_file, delimiter=sep):
                userId = row[0]
                user_email = row[6]
                user_emails_dictionary[userId].append(user_email)
        logger.info("Loaded emails for %d users", len(user_emails_dictionary))
        return user_emails_dictionary

    def get_mapped_status(self, status_to_map):
        # Map statuses as follows;
        # "serverHold” fields will map to hold clientHold to hold
        # and any ok state should map to Ready.
        # Check if there are any statuses that are not
        # serverhold, client hold or OK in the original data set.
        status_maps = {
            "hold": TransitionDomain.StatusChoices.HOLD,
            "serverhold": TransitionDomain.StatusChoices.HOLD,
            "clienthold": TransitionDomain.StatusChoices.HOLD,
            "created": TransitionDomain.StatusChoices.READY,
            "ok": TransitionDomain.StatusChoices.READY,
        }
        return status_maps[status_to_map]

    def print_summary_duplications(
        self, duplicate_domain_user_combos, duplicate_domains, users_without_email
    ):
        totalDupDomainUserPairs = len(duplicate_domain_user_combos)
        totalDupDomains = len(duplicate_domains)
        total_users_without_email = len(users_without_email)
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

                    {totalDupDomainUserPairs} DOMAIN - USER pairs
                    were NOT unique in the supplied data files;

                    {temp_dupPairsAsString}

                    {totalDupDomains} DOMAINS were NOT unique in
                    the supplied data files;

                    {temp_dupDomainsAsString}
                    {termColors.ENDC}"""
            )

    def print_summary_status_findings(self, domains_without_status, outlier_statuses):
        total_domains_without_status = len(domains_without_status)
        total_outlier_statuses = len(outlier_statuses)
        if total_domains_without_status > 0:
            temp_arrayToString = "{}".format(
                ", ".join(map(str, domains_without_status))
            )
            logger.warning(
                f"""{termColors.WARNING}

                --------------------------------------------
                Found {total_domains_without_status} domains
                without a status (defaulted to READY)
                ---------------------------------------------

                {temp_arrayToString}
                {termColors.ENDC}"""
            )

        if total_outlier_statuses > 0:
            temp_arrayToString = "{}".format(
                ", ".join(map(str, outlier_statuses))
            )  # noqa
            logger.warning(
                f"""{termColors.WARNING}

                --------------------------------------------
                Found {total_outlier_statuses} unaccounted
                for statuses-
                --------------------------------------------

                No mappings found for the following statuses
                (defaulted to Ready):

                {temp_arrayToString}
                {termColors.ENDC}"""
            )
