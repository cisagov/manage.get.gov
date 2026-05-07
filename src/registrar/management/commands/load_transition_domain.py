import json
import os
import sys
import csv
import logging
import argparse

from collections import defaultdict
from django.conf import settings

from django.core.management import BaseCommand
from registrar.management.commands.utility.epp_data_containers import EnumFilenames

from registrar.models import TransitionDomain

from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)

from .utility.transition_domain_arguments import TransitionDomainArguments
from .utility.extra_transition_domain_helper import LoadExtraTransitionDomain

logger = logging.getLogger(__name__)


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
            "migration_json_filename",
            help=("A JSON file that holds the location and filenames" "of all the data files used for migrations"),
        )

        parser.add_argument("--sep", default="|", help="Delimiter character")

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument("--limitParse", default=0, help="Sets max number of entries to load")

        parser.add_argument(
            "--resetTable",
            help="Deletes all data in the TransitionDomain table",
            action=argparse.BooleanOptionalAction,
        )

        # This option should only be available when developing locally.
        # This should not be available to the end user.
        if settings.DEBUG:
            parser.add_argument(
                "--infer_filenames",
                action=argparse.BooleanOptionalAction,
                help="Determines if we should infer filenames or not."
                "Recommended to be enabled only in a development or testing setting.",
            )

        parser.add_argument("--directory", default="migrationdata", help="Desired directory")
        parser.add_argument(
            "--domain_contacts_filename",
            help="Data file with domain contact information",
        )
        parser.add_argument(
            "--contacts_filename",
            help="Data file with contact information",
        )
        parser.add_argument(
            "--domain_statuses_filename",
            help="Data file with domain status information",
        )
        parser.add_argument(
            "--agency_adhoc_filename",
            default=EnumFilenames.AGENCY_ADHOC.value[1],
            help="Defines the filename for agency adhocs",
        )
        parser.add_argument(
            "--domain_additional_filename",
            default=EnumFilenames.DOMAIN_ADDITIONAL.value[1],
            help="Defines the filename for additional domain data",
        )
        parser.add_argument(
            "--domain_escrow_filename",
            default=EnumFilenames.DOMAIN_ESCROW.value[1],
            help="Defines the filename for creation/expiration domain data",
        )
        parser.add_argument(
            "--domain_adhoc_filename",
            default=EnumFilenames.DOMAIN_ADHOC.value[1],
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument(
            "--organization_adhoc_filename",
            default=EnumFilenames.ORGANIZATION_ADHOC.value[1],
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument(
            "--authority_adhoc_filename",
            default=EnumFilenames.AUTHORITY_ADHOC.value[1],
            help="Defines the filename for domain type adhocs",
        )

    def print_debug_mode_statements(self, debug_on: bool, debug_max_entries_to_parse: int):
        """Prints additional terminal statements to indicate if --debug
        or --limitParse are in use"""
        if debug_on:
            logger.info(f"""{TerminalColors.OKCYAN}
                ----------DEBUG MODE ON----------
                Detailed print statements activated.
                {TerminalColors.ENDC}
                """)
        if debug_max_entries_to_parse > 0:
            logger.info(f"""{TerminalColors.OKCYAN}
                ----------LIMITER ON----------
                Parsing of entries will be limited to
                {debug_max_entries_to_parse} lines per file.")
                Detailed print statements activated.
                {TerminalColors.ENDC}
                """)

    def get_domain_user_dict(self, domain_statuses_filename: str, sep: str) -> defaultdict[str, str]:
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

    def get_user_emails_dict(self, contacts_filename: str, sep) -> defaultdict[str, str]:
        """Creates mapping of userId -> emails"""
        user_emails_dictionary = defaultdict(str)
        logger.info("Reading contacts data file %s", contacts_filename)
        with open(contacts_filename, "r") as contacts_file:
            for row in csv.reader(contacts_file, delimiter=sep):
                if row != []:
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
            "unknown": TransitionDomain.StatusChoices.UNKNOWN,
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
            users_without_email_as_string = "{}".format(", ".join(map(str, duplicate_domain_user_combos)))
            logger.warning(
                f"{TerminalColors.YELLOW} No e-mails found for users: {users_without_email_as_string}"  # noqa
            )
        if total_duplicate_pairs > 0 or total_duplicate_domains > 0:
            duplicate_pairs_as_string = "{}".format(", ".join(map(str, duplicate_domain_user_combos)))
            duplicate_domains_as_string = "{}".format(", ".join(map(str, duplicate_domains)))
            logger.warning(f"""{TerminalColors.YELLOW}

                    ----DUPLICATES FOUND-----

                    {total_duplicate_pairs} DOMAIN - USER pairs
                    were NOT unique in the supplied data files;

                    {duplicate_pairs_as_string}

                    {total_duplicate_domains} DOMAINS were NOT unique in
                    the supplied data files;

                    {duplicate_domains_as_string}
                    {TerminalColors.ENDC}""")

    def print_summary_status_findings(self, domains_without_status: list[str], outlier_statuses: list[str]):
        """Called at the end of the script execution to print out a summary of
        status anomolies in the imported Verisign data.  Currently, we check for:
        - domains without a status
        - any statuses not accounted for in our status mappings (see
        get_mapped_status() function)
        """
        total_domains_without_status = len(domains_without_status)
        total_outlier_statuses = len(outlier_statuses)
        if total_domains_without_status > 0:
            domains_without_status_as_string = "{}".format(", ".join(map(str, domains_without_status)))
            logger.warning(f"""{TerminalColors.YELLOW}

                --------------------------------------------
                Found {total_domains_without_status} domains
                without a status (defaulted to READY)
                ---------------------------------------------

                {domains_without_status_as_string}
                {TerminalColors.ENDC}""")

        if total_outlier_statuses > 0:
            domains_without_status_as_string = "{}".format(", ".join(map(str, outlier_statuses)))  # noqa
            logger.warning(f"""{TerminalColors.YELLOW}

                --------------------------------------------
                Found {total_outlier_statuses} unaccounted
                for statuses
                --------------------------------------------

                No mappings found for the following statuses
                (defaulted to Ready):

                {domains_without_status_as_string}
                {TerminalColors.ENDC}""")

    def prompt_table_reset(self):
        """Brings up a prompt in the terminal asking
        if the user wishes to delete data in the
        TransitionDomain table.  If the user confirms,
        deletes all the data in the TransitionDomain table"""
        confirm_reset = TerminalHelper.query_yes_no(f"""
            {TerminalColors.FAIL}
            WARNING: Resetting the table will permanently delete all
            the data!
            Are you sure you want to continue?{TerminalColors.ENDC}""")
        if confirm_reset:
            logger.info(f"""{TerminalColors.YELLOW}
            ----------Clearing Table Data----------
            (please wait)
            {TerminalColors.ENDC}""")
            TransitionDomain.objects.all().delete()

    def parse_extra(self, options):
        """Loads additional information for each TransitionDomain
        object based off supplied files."""
        try:
            # Parse data from files
            extra_data = LoadExtraTransitionDomain(options)

            # Update every TransitionDomain object where applicable
            extra_data.update_transition_domain_models()
        except Exception as err:
            logger.error(f"Could not load additional TransitionDomain data. {err}")
            raise err

    def handle(  # noqa: C901
        self,
        migration_json_filename,
        **options,
    ):
        """Parse the data files and create TransitionDomains."""
        if not settings.DEBUG:
            options["infer_filenames"] = False

        args = TransitionDomainArguments(**options)

        # Desired directory for additional TransitionDomain data
        # (In the event they are stored seperately)
        directory = args.directory
        # Add a slash if the last character isn't one
        if directory and directory[-1] != "/":
            directory += "/"

        json_filepath = directory + migration_json_filename
        # Process JSON file #
        # If a JSON was provided, use its values instead of defaults.
        # TODO: there is no way to discern user overrides from those arg’s defaults.
        with open(json_filepath, "r") as jsonFile:
            # load JSON object as a dictionary
            try:
                data = json.load(jsonFile)
                # Create an instance of TransitionDomainArguments
                # Iterate over the data from the JSON file
                for key, value in data.items():
                    # Check if the key exists in TransitionDomainArguments
                    if hasattr(args, key):
                        # If it does, update the options
                        options[key] = value
            except Exception as err:
                logger.error(
                    f"{TerminalColors.FAIL}"
                    "There was an error loading "
                    "the JSON responsible for providing filepaths."
                    f"{TerminalColors.ENDC}"
                )
                raise err

        sep = args.sep

        # If --resetTable was used, prompt user to confirm
        # deletion of table data
        if args.resetTable:
            self.prompt_table_reset()

        # Get --debug argument
        debug_on = args.debug

        # Get --LimitParse argument
        debug_max_entries_to_parse = int(args.limitParse)  # set to 0 to parse all entries

        # Variables for Additional TransitionDomain Information #

        # Main script filenames - these do not have defaults
        domain_contacts_filename = None
        try:
            domain_contacts_filename = directory + options.get("domain_contacts_filename")
        except TypeError:
            logger.error(
                f"Invalid filename of '{args.domain_contacts_filename}'" " was provided for domain_contacts_filename"
            )

        contacts_filename = None
        try:
            contacts_filename = directory + options.get("contacts_filename")
        except TypeError:
            logger.error(f"Invalid filename of '{args.contacts_filename}'" " was provided for contacts_filename")

        domain_statuses_filename = None
        try:
            domain_statuses_filename = directory + options.get("domain_statuses_filename")
        except TypeError:
            logger.error(
                f"Invalid filename of '{args.domain_statuses_filename}'" " was provided for domain_statuses_filename"
            )

        # Agency information
        agency_adhoc_filename = options.get("agency_adhoc_filename")
        # Federal agency / organization type information
        domain_adhoc_filename = options.get("domain_adhoc_filename")
        # Organization name information
        organization_adhoc_filename = options.get("organization_adhoc_filename")
        # Creation date / expiration date information
        domain_escrow_filename = options.get("domain_escrow_filename")

        # Container for all additional TransitionDomain information
        domain_additional_filename = options.get("domain_additional_filename")

        # print message to terminal about which args are in use
        self.print_debug_mode_statements(debug_on, debug_max_entries_to_parse)

        filenames = [
            agency_adhoc_filename,
            domain_adhoc_filename,
            organization_adhoc_filename,
            domain_escrow_filename,
            domain_additional_filename,
        ]

        # Do a top-level check to see if these files exist
        for filename in filenames:
            if not isinstance(filename, str):
                raise TypeError(f"Filename must be a string, got {type(filename).__name__}")
            full_path = os.path.join(directory, filename)
            if not os.path.isfile(full_path):
                raise FileNotFoundError(full_path)

        # STEP 1:
        # Create mapping of domain name -> status
        domain_status_dictionary = self.get_domain_user_dict(domain_statuses_filename, sep)

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

                TerminalHelper.print_conditional(
                    True,
                    f"Processing item {total_rows_parsed}: {new_entry_domain_name}",
                )

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
                    (x for x in to_create if x.username == new_entry_email and x.domain_name == new_entry_domain_name),
                    None,
                )
                if existing_domain is not None:
                    # DEBUG:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"{TerminalColors.YELLOW} DUPLICATE file entries found for domain: {new_entry_domain_name} {TerminalColors.ENDC}",  # noqa
                    )
                    if new_entry_domain_name not in duplicate_domains:
                        duplicate_domains.append(new_entry_domain_name)
                if existing_domain_user_pair is not None:
                    # DEBUG:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"""{TerminalColors.YELLOW} DUPLICATE file entries found for domain - user {TerminalColors.BackgroundLightYellow} PAIR {TerminalColors.ENDC}{TerminalColors.YELLOW}:  
                        {new_entry_domain_name} - {new_entry_email} {TerminalColors.ENDC}""",  # noqa
                    )
                    if existing_domain_user_pair not in duplicate_domain_user_combos:
                        duplicate_domain_user_combos.append(existing_domain_user_pair)
                else:
                    entry_exists = TransitionDomain.objects.filter(
                        username=new_entry_email, domain_name=new_entry_domain_name
                    ).exists()
                    if entry_exists:
                        try:
                            existing_entry = TransitionDomain.objects.get(
                                username=new_entry_email,
                                domain_name=new_entry_domain_name,
                            )

                            if not existing_entry.processed:
                                if existing_entry.status != new_entry_status:
                                    TerminalHelper.print_conditional(
                                        debug_on,
                                        f"{TerminalColors.OKCYAN}"
                                        f"Updating entry: {existing_entry}"
                                        f"Status: {existing_entry.status} > {new_entry_status}"  # noqa
                                        f"Email Sent: {existing_entry.email_sent} > {new_entry_emailSent}"  # noqa
                                        f"{TerminalColors.ENDC}",
                                    )
                                    existing_entry.status = new_entry_status
                                existing_entry.email_sent = new_entry_emailSent
                                existing_entry.save()
                            else:
                                TerminalHelper.print_conditional(
                                    debug_on,
                                    f"{TerminalColors.YELLOW}"
                                    f"Skipping update on processed domain: {existing_entry}"
                                    f"{TerminalColors.ENDC}",
                                )

                        except TransitionDomain.MultipleObjectsReturned:
                            logger.info(
                                f"{TerminalColors.FAIL}"
                                f"!!! ERROR: duplicate entries exist in the"
                                f"transtion_domain table for domain:"
                                f"{new_entry_domain_name}"
                                f"----------TERMINATING----------"
                            )
                            sys.exit()

                    else:
                        # no matching entry, make one
                        new_entry = TransitionDomain(
                            username=new_entry_email,
                            domain_name=new_entry_domain_name,
                            status=new_entry_status,
                            email_sent=new_entry_emailSent,
                            processed=False,
                        )
                        to_create.append(new_entry)
                        total_new_entries += 1

                        # DEBUG:
                        TerminalHelper.print_conditional(
                            debug_on,
                            f"{TerminalColors.OKCYAN} Adding entry {total_new_entries}: {new_entry} {TerminalColors.ENDC}",  # noqa
                        )

                # Check Parse limit and exit loop if needed
                if total_rows_parsed >= debug_max_entries_to_parse and debug_max_entries_to_parse != 0:
                    logger.info(
                        f"{TerminalColors.YELLOW}"
                        f"----PARSE LIMIT REACHED.  HALTING PARSER.----"
                        f"{TerminalColors.ENDC}"
                    )
                    break

        TransitionDomain.objects.bulk_create(to_create)
        # Print a summary of findings (duplicate entries,
        # missing data..etc.)
        self.print_summary_duplications(duplicate_domain_user_combos, duplicate_domains, users_without_email)
        self.print_summary_status_findings(domains_without_status, outlier_statuses)

        logger.info(f"""{TerminalColors.OKGREEN}
            ============= FINISHED ===============
            Created {total_new_entries} transition domain entries,
            Updated {total_updated_domain_entries} transition domain entries

            {TerminalColors.YELLOW}
            ----- DUPLICATES FOUND -----
            {len(duplicate_domain_user_combos)} DOMAIN - USER pairs
            were NOT unique in the supplied data files.
            {len(duplicate_domains)} DOMAINS were NOT unique in
            the supplied data files.

            ----- STATUSES -----
            {len(domains_without_status)} DOMAINS had NO status (defaulted to READY).
            {len(outlier_statuses)} Statuses were invalid (defaulted to READY).

            {TerminalColors.ENDC}
            """)

        # Print a summary of findings (duplicate entries,
        # missing data..etc.)
        self.print_summary_duplications(duplicate_domain_user_combos, duplicate_domains, users_without_email)
        self.print_summary_status_findings(domains_without_status, outlier_statuses)

        logger.info(f"""{TerminalColors.OKGREEN}
            ============= FINISHED ===============
            Created {total_new_entries} transition domain entries,
            Updated {total_updated_domain_entries} transition domain entries

            {TerminalColors.YELLOW}
            ----- DUPLICATES FOUND -----
            {len(duplicate_domain_user_combos)} DOMAIN - USER pairs
            were NOT unique in the supplied data files.
            {len(duplicate_domains)} DOMAINS were NOT unique in
            the supplied data files.

            ----- STATUSES -----
            {len(domains_without_status)} DOMAINS had NO status (defaulted to READY).
            {len(outlier_statuses)} Statuses were invalid (defaulted to READY).

            {TerminalColors.ENDC}
            """)

        # Prompt the user if they want to load additional data on the domains
        title = "Do you wish to load additional data for TransitionDomains?"
        proceed = TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            !!! ENSURE THAT ALL FILENAMES ARE CORRECT BEFORE PROCEEDING
            ==Master data file==
            domain_additional_filename: {domain_additional_filename}

            ==Federal agency information==
            agency_adhoc_filename: {agency_adhoc_filename}

            ==Federal type / organization type information==
            domain_adhoc_filename: {domain_adhoc_filename}

            ==Organization name information==
            organization_adhoc_filename: {organization_adhoc_filename}

            ==Creation date / expiration date information==
            domain_escrow_filename: {domain_escrow_filename}

            ==Containing directory==
            directory: {directory}
            """,
            prompt_title=title,
        )
        if proceed:
            arguments = TransitionDomainArguments(**options)
            self.parse_extra(arguments)
