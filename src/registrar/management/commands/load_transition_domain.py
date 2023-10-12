"""Load domain invitations for existing domains and their contacts."""

import sys
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
    YELLOW = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BackgroundLightYellow = "\033[103m"


def query_yes_no(question: str, default="yes") -> bool:
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
    help = """Loads data for domains that are in transition
    (populates transition_domain model objects)."""

    def add_arguments(self, parser):
        """Add our three filename arguments (in order: domain contacts,
        contacts, and domain statuses)
        OPTIONAL ARGUMENTS:
        --sep
        The default delimiter is set to "|", but may be changed using --sep
        --debug
        A boolean (default to true), which activates additional print statements
        --limitParse
        Used to set a limit for the number of data entries to insert.  Set to 0
        (or just don't use this argument) to parse every entry.
        --resetTable
        Use this to trigger a prompt for deleting all table entries.  Useful
        for testing purposes, but USE WITH CAUTION
        """
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

    def print_debug_mode_statements(
        self, debug_on: bool, debug_max_entries_to_parse: int
    ):
        """Prints additional terminal statements to indicate if --debug
        or --limitParse are in use"""
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

    def get_domain_user_dict(
        self, domain_statuses_filename: str, sep: str
    ) -> defaultdict[str, str]:
        """Creates a mapping of domain name -> status"""
        domain_status_dictionary = defaultdict(str)
        logger.info("Reading domain statuses data file %s", domain_statuses_filename)
        with open(domain_statuses_filename, "r") as domain_statuses_file:  # noqa
            for row in csv.reader(domain_statuses_file, delimiter=sep):
                domainName = row[0].lower()
                domainStatus = row[1].lower()
                domain_status_dictionary[domainName] = domainStatus
        logger.info("Loaded statuses for %d domains", len(domain_status_dictionary))
        return domain_status_dictionary

    def get_user_emails_dict(
        self, contacts_filename: str, sep
    ) -> defaultdict[str, str]:
        """Creates mapping of userId -> emails"""
        user_emails_dictionary = defaultdict(str)
        logger.info("Reading domain-contacts data file %s", contacts_filename)
        with open(contacts_filename, "r") as contacts_file:
            for row in csv.reader(contacts_file, delimiter=sep):
                user_id = row[0]
                user_email = row[6]
                user_emails_dictionary[user_id] = user_email
        logger.info("Loaded emails for %d users", len(user_emails_dictionary))
        return user_emails_dictionary

    def get_mapped_status(self, status_to_map: str):
        """
        Given a verisign domain status, return a corresponding
        status defined for our domains.

        We map statuses as follows;
        "serverHold” fields will map to hold, clientHold to hold
        and any ok state should map to Ready.
        """
        status_maps = {
            "hold": TransitionDomain.StatusChoices.ON_HOLD,
            "serverhold": TransitionDomain.StatusChoices.ON_HOLD,
            "clienthold": TransitionDomain.StatusChoices.ON_HOLD,
            "created": TransitionDomain.StatusChoices.READY,
            "ok": TransitionDomain.StatusChoices.READY,
        }
        mapped_status = status_maps.get(status_to_map)
        return mapped_status

    def print_summary_duplications(
        self,
        duplicate_domain_user_combos: list[TransitionDomain],
        duplicate_domains: list[TransitionDomain],
        users_without_email: list[str],
    ):
        """Called at the end of the script execution to print out a summary of
        data anomalies in the imported Verisign data.  Currently, we check for:
        - duplicate domains
        - duplicate domain - user pairs
        - any users without e-mails (this would likely only happen if the contacts
        file is missing a user found in the domain_contacts file)
        """
        total_duplicate_pairs = len(duplicate_domain_user_combos)
        total_duplicate_domains = len(duplicate_domains)
        total_users_without_email = len(users_without_email)
        if total_users_without_email > 0:
            logger.warning(
                "No e-mails found for users: {}".format(
                    ", ".join(map(str, users_without_email))
                )
            )
        if total_duplicate_pairs > 0 or total_duplicate_domains > 0:
            duplicate_pairs_as_string = "{}".format(
                ", ".join(map(str, duplicate_domain_user_combos))
            )
            duplicate_domains_as_string = "{}".format(
                ", ".join(map(str, duplicate_domains))
            )
            logger.warning(
                f"""{termColors.YELLOW}

                    ----DUPLICATES FOUND-----

                    {total_duplicate_pairs} DOMAIN - USER pairs
                    were NOT unique in the supplied data files;

                    {duplicate_pairs_as_string}

                    {total_duplicate_domains} DOMAINS were NOT unique in
                    the supplied data files;

                    {duplicate_domains_as_string}
                    {termColors.ENDC}"""
            )

    def print_summary_status_findings(
        self, domains_without_status: list[str], outlier_statuses: list[str]
    ):
        """Called at the end of the script execution to print out a summary of
        status anomolies in the imported Verisign data.  Currently, we check for:
        - domains without a status
        - any statuses not accounted for in our status mappings (see
        get_mapped_status() function)
        """
        total_domains_without_status = len(domains_without_status)
        total_outlier_statuses = len(outlier_statuses)
        if total_domains_without_status > 0:
            domains_without_status_as_string = "{}".format(
                ", ".join(map(str, domains_without_status))
            )
            logger.warning(
                f"""{termColors.YELLOW}

                --------------------------------------------
                Found {total_domains_without_status} domains
                without a status (defaulted to READY)
                ---------------------------------------------

                {domains_without_status_as_string}
                {termColors.ENDC}"""
            )

        if total_outlier_statuses > 0:
            domains_without_status_as_string = "{}".format(
                ", ".join(map(str, outlier_statuses))
            )  # noqa
            logger.warning(
                f"""{termColors.YELLOW}

                --------------------------------------------
                Found {total_outlier_statuses} unaccounted
                for statuses-
                --------------------------------------------

                No mappings found for the following statuses
                (defaulted to Ready):

                {domains_without_status_as_string}
                {termColors.ENDC}"""
            )
    

    def print_debug(self, print_condition: bool, print_statement: str):
        """This function reduces complexity of debug statements
        in other functions.
        It uses the logger to write the given print_statement to the
        terminal if print_condition is TRUE"""
        # DEBUG:
        if print_condition:
            logger.info(print_statement)


    def prompt_table_reset():
        """Brings up a prompt in the terminal asking
        if the user wishes to delete data in the
        TransitionDomain table.  If the user confirms,
        deletes all the data in the TransitionDomain table"""
        confirm_reset = query_yes_no(
            f"""
            {termColors.FAIL}
            WARNING: Resetting the table will permanently delete all
            the data!
            Are you sure you want to continue?{termColors.ENDC}"""
        )
        if confirm_reset:
            logger.info(
                f"""{termColors.YELLOW}
            ----------Clearing Table Data----------
            (please wait)
            {termColors.ENDC}"""
            )
            TransitionDomain.objects.all().delete()

    def handle(
        self,
        domain_contacts_filename,
        contacts_filename,
        domain_statuses_filename,
        **options,
    ):
        """Parse the data files and create TransitionDomains."""
        sep = options.get("sep")

        # If --resetTable was used, prompt user to confirm
        # deletion of table data
        if options.get("resetTable"):
            self.prompt_table_reset()

        # Get --debug argument
        debug_on = options.get("debug")

        # Get --LimitParse argument
        debug_max_entries_to_parse = int(
            options.get("limitParse")
        )  # set to 0 to parse all entries

        # print message to terminal about which args are in use
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
        # Parse the domain_contacts file and create TransitionDomain objects,
        # using the dictionaries from steps 1 & 2 to lookup needed information.

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

        # Start parsing the main file and create TransitionDomain objects
        logger.info("Reading domain-contacts data file %s", domain_contacts_filename)
        with open(domain_contacts_filename, "r") as domain_contacts_file:
            for row in csv.reader(domain_contacts_file, delimiter=sep):
                total_rows_parsed += 1

                # fields are just domain, userid, role
                # lowercase the domain names
                new_entry_domain_name = row[0].lower()
                user_id = row[1]

                new_entry_status = TransitionDomain.StatusChoices.READY
                new_entry_email = ""
                new_entry_emailSent = False  # set to False by default

                # PART 1: Get the status
                if new_entry_domain_name not in domain_status_dictionary:
                    # This domain has no status...default to "Create"
                    # (For data analysis purposes, add domain name 
                    # to list of all domains without status 
                    # (avoid duplicate entries))
                    if new_entry_domain_name not in domains_without_status:
                        domains_without_status.append(new_entry_domain_name)
                else:
                    # Map the status 
                    original_status = domain_status_dictionary[new_entry_domain_name]
                    mapped_status = self.get_mapped_status(original_status)
                    if mapped_status is None:
                        # (For data analysis purposes, check for any statuses 
                        # that don't have a mapping and add to list 
                        # of "outlier statuses")
                        logger.info("Unknown status: " + original_status)
                        outlier_statuses.append(original_status)
                    else:
                        new_entry_status = mapped_status
                
                # PART 2: Get the e-mail
                if user_id not in user_emails_dictionary:
                    # this user has no e-mail...this should never happen
                    if user_id not in users_without_email:
                        users_without_email.append(user_id)
                else:
                    new_entry_email = user_emails_dictionary[user_id]

                # PART 3: Create the transition domain object
                # Check for duplicate data in the file we are
                # parsing so we do not add duplicates
                # NOTE: Currently, we allow duplicate domains,
                # but not duplicate domain-user pairs.
                # However, track duplicate domains for now,
                # since we are still deciding on whether
                # to make this field unique or not. ~10/25/2023
                existing_domain = next(
                    (x for x in to_create if x.domain_name == new_entry_domain_name),
                    None,
                )
                existing_domain_user_pair = next(
                    (
                        x
                        for x in to_create
                        if x.username == new_entry_email
                        and x.domain_name == new_entry_domain_name
                    ),
                    None,
                )
                if existing_domain is not None:
                    # DEBUG:
                    self.print_debug(
                        debug_on,
                        f"{termColors.YELLOW} DUPLICATE Verisign entries found for domain: {new_entry_domain_name} {termColors.ENDC}"  # noqa
                        )
                    if new_entry_domain_name not in duplicate_domains:
                        duplicate_domains.append(new_entry_domain_name)
                if existing_domain_user_pair is not None:
                    # DEBUG:
                    self.print_debug(
                        debug_on,
                        f"""{termColors.YELLOW} DUPLICATE Verisign entries found for domain - user {termColors.BackgroundLightYellow} PAIR {termColors.ENDC}{termColors.YELLOW}:  
                        {new_entry_domain_name} - {new_entry_email} {termColors.ENDC}"""  # noqa
                        )
                    if existing_domain_user_pair not in duplicate_domain_user_combos:
                        duplicate_domain_user_combos.append(existing_domain_user_pair)
                else:
                    try:
                        entry_exists = TransitionDomain.objects.exists(
                            username=new_entry_email, domain_name=new_entry_domain_name
                        )
                        if(entry_exists):
                            existing_entry = TransitionDomain.objects.get(
                                username=new_entry_email, domain_name=new_entry_domain_name
                            )

                            if existing_entry.status != new_entry_status:
                                # DEBUG:
                                self.print_debug(
                                    debug_on,
                                    f"{termColors.OKCYAN}"
                                    f"Updating entry: {existing_entry}"
                                    f"Status: {existing_entry.status} > {new_entry_status}"  # noqa
                                    f"Email Sent: {existing_entry.email_sent} > {new_entry_emailSent}"  # noqa
                                    f"{termColors.ENDC}"
                                    )
                                existing_entry.status = new_entry_status

                        existing_entry.email_sent = new_entry_emailSent
                        existing_entry.save()
                    except TransitionDomain.DoesNotExist:
                        # no matching entry, make one
                        new_entry = TransitionDomain(
                            username=new_entry_email,
                            domain_name=new_entry_domain_name,
                            status=new_entry_status,
                            email_sent=new_entry_emailSent,
                        )
                        to_create.append(new_entry)
                        total_new_entries += 1

                        # DEBUG:
                        self.print_debug(
                            debug_on,
                            f"{termColors.OKCYAN} Adding entry {total_new_entries}: {new_entry} {termColors.ENDC}"  # noqa
                        )
                    except TransitionDomain.MultipleObjectsReturned:
                        logger.info(
                            f"{termColors.FAIL}"
                            f"!!! ERROR: duplicate entries exist in the"
                            f"transtion_domain table for domain:"
                            f"{new_entry_domain_name}"
                            f"----------TERMINATING----------"
                        )
                        sys.exit()

                # DEBUG:
                if (total_rows_parsed >= debug_max_entries_to_parse
                    and debug_max_entries_to_parse != 0):
                        logger.info(
                            f"{termColors.YELLOW}"
                            f"----PARSE LIMIT REACHED.  HALTING PARSER.----"
                            f"{termColors.ENDC}"
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
