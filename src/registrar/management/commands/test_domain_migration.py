import logging
import argparse
import os

from django.test import Client

from django_fsm import TransitionNotAllowed  # type: ignore

from django.core.management import BaseCommand
from django.contrib.auth import get_user_model

from registrar.models import TransitionDomain
from registrar.models import Domain
from registrar.models import DomainInvitation
from registrar.models.domain_information import DomainInformation

from registrar.management.commands.utility.terminal_helper import TerminalColors
from registrar.management.commands.utility.terminal_helper import TerminalHelper

from registrar.management.commands.load_transition_domain import (
    Command as load_transition_domain_command,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """ """

    def add_arguments(self, parser):
        """
        OPTIONAL ARGUMENTS:
        --debug
        A boolean (default to true), which activates additional print statements
        """

        parser.add_argument(
            "--runLoaders",
            help="Runs all scripts (in sequence) for transition domain migrations",
            action=argparse.BooleanOptionalAction,
        )

        parser.add_argument(
            "--triggerLogins",
            help="Simulates a user login for each user in domain invitation",
            action=argparse.BooleanOptionalAction,
        )

        # The following file arguments have default values for running in the sandbox
        parser.add_argument(
            "--loaderDirectory",
            default="migrationData",
            help="The location of the files used for load_transition_domain migration script",
        )
        parser.add_argument(
            "--loaderFilenames",
            default="escrow_domain_contacts.daily.gov.GOV.txt escrow_contacts.daily.gov.GOV.txt escrow_domain_statuses.daily.gov.GOV.txt",
            help="""The files used for load_transition_domain migration script.  
            Must appear IN ORDER and separated by spaces: 
            domain_contacts_filename.txt contacts_filename.txt domain_statuses_filename.txt
            
            where...
            - domain_contacts_filename is the Data file with domain contact information
            - contacts_filename is the Data file with contact information
            - domain_statuses_filename is the Data file with domain status information""",
        )

        # parser.add_argument(
        #     "domain_contacts_filename",
        #     default="escrow_domain_contacts.daily.gov.GOV.txt",
        #     help="Data file with domain contact information"
        # )
        # parser.add_argument(
        #     "contacts_filename",
        #     default="escrow_contacts.daily.gov.GOV.txt",
        #     help="Data file with contact information",
        # )
        # parser.add_argument(
        #     "domain_statuses_filename",
        #     default="escrow_domain_statuses.daily.gov.GOV.txt",
        #     help="Data file with domain status information"
        # )

        parser.add_argument(
            "--sep", default="|", help="Delimiter character for the loader files"
        )

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse", default=0, help="Sets max number of entries to load"
        )

        parser.add_argument(
            "--resetTable",
            help="Deletes all data in the TransitionDomain table",
            action=argparse.BooleanOptionalAction,
        )

    def print_debug_mode_statements(self, debug_on: bool):
        """Prints additional terminal statements to indicate if --debug
        or --limitParse are in use"""
        self.print_debug(
            debug_on,
            f"""{TerminalColors.OKCYAN}
            ----------DEBUG MODE ON----------
            Detailed print statements activated.
            {TerminalColors.ENDC}
            """,
        )

    def print_debug(self, print_condition: bool, print_statement: str):
        """This function reduces complexity of debug statements
        in other functions.
        It uses the logger to write the given print_statement to the
        terminal if print_condition is TRUE"""
        # DEBUG:
        if print_condition:
            logger.info(print_statement)

    def compare_tables(self, debug_on):
        logger.info(
            f"""{TerminalColors.OKCYAN}
            ============= BEGINNING ANALYSIS ===============
            {TerminalColors.ENDC}
            """
        )

        # TODO: would filteredRelation be faster?
        for transition_domain in TransitionDomain.objects.all():  # DEBUG:
            transition_domain_name = transition_domain.domain_name
            transition_domain_email = transition_domain.username

            self.print_debug(
                debug_on,
                f"{TerminalColors.OKCYAN}Checking: {transition_domain_name} {TerminalColors.ENDC}",  # noqa
            )

            missing_domains = []
            duplicate_domains = []
            missing_domain_informations = []
            missing_domain_invites = []

            # Check Domain table
            matching_domains = Domain.objects.filter(name=transition_domain_name)
            # Check Domain Information table
            matching_domain_informations = DomainInformation.objects.filter(
                domain__name=transition_domain_name
            )
            # Check Domain Invitation table
            matching_domain_invitations = DomainInvitation.objects.filter(
                email=transition_domain_email.lower(),
                domain__name=transition_domain_name,
            )

            if len(matching_domains) == 0:
                missing_domains.append(transition_domain_name)
            elif len(matching_domains) > 1:
                duplicate_domains.append(transition_domain_name)
            if len(matching_domain_informations) == 0:
                missing_domain_informations.append(transition_domain_name)
            if len(matching_domain_invitations) == 0:
                missing_domain_invites.append(transition_domain_name)

        total_missing_domains = len(missing_domains)
        total_duplicate_domains = len(duplicate_domains)
        total_missing_domain_informations = len(missing_domain_informations)
        total_missing_domain_invitations = len(missing_domain_invites)

        missing_domains_as_string = "{}".format(", ".join(map(str, missing_domains)))
        duplicate_domains_as_string = "{}".format(
            ", ".join(map(str, duplicate_domains))
        )
        missing_domain_informations_as_string = "{}".format(
            ", ".join(map(str, missing_domain_informations))
        )
        missing_domain_invites_as_string = "{}".format(
            ", ".join(map(str, missing_domain_invites))
        )

        logger.info(
            f"""{TerminalColors.OKGREEN}
            ============= FINISHED ANALYSIS ===============
            
            {total_missing_domains} Missing Domains:
            (These are transition domains that are missing from the Domain Table)
            {TerminalColors.YELLOW}{missing_domains_as_string}{TerminalColors.OKGREEN}

            {total_duplicate_domains} Duplicate Domains:
            (These are transition domains which have duplicate entries in the Domain Table)
            {TerminalColors.YELLOW}{duplicate_domains_as_string}{TerminalColors.OKGREEN}

            {total_missing_domain_informations} Domains Information Entries missing:
            (These are transition domains which have no entries in the Domain Information Table)
            {TerminalColors.YELLOW}{missing_domain_informations_as_string}{TerminalColors.OKGREEN}

            {total_missing_domain_invitations} Domain Invitations missing:
            (These are transition domains which have no entires in the Domain Invitation Table)
            {TerminalColors.YELLOW}{missing_domain_invites_as_string}{TerminalColors.OKGREEN}
            {TerminalColors.ENDC}
            """
        )

    def run_load_transition_domain_script(
        self,
        file_location,
        domain_contacts_filename,
        contacts_filename,
        domain_statuses_filename,
        sep,
        reset_table,
        debug_on,
        debug_max_entries_to_parse,
    ):
        load_transition_domain_command_string = "./manage.py load_transition_domain "
        load_transition_domain_command_string += (
            file_location + domain_contacts_filename + " "
        )
        load_transition_domain_command_string += file_location + contacts_filename + " "
        load_transition_domain_command_string += (
            file_location + domain_statuses_filename + " "
        )

        if sep is not None and sep != "|":
            load_transition_domain_command_string += f"--sep {sep} "

        if reset_table:
            load_transition_domain_command_string += "--resetTable "

        if debug_on:
            load_transition_domain_command_string += "--debug "

        if debug_max_entries_to_parse > 0:
            load_transition_domain_command_string += (
                f"--limitParse {debug_max_entries_to_parse} "
            )

        proceed_load_transition_domain = TerminalHelper.query_yes_no(
            f"""{TerminalColors.OKCYAN}
            =====================================
            Running load_transition_domain script
            =====================================
            
            {load_transition_domain_command_string}
            {TerminalColors.FAIL}
            Proceed?
            {TerminalColors.ENDC}"""
        )

        if not proceed_load_transition_domain:
            return
        logger.info(
            f"""{TerminalColors.OKCYAN}
        ==== EXECUTING... ====
        {TerminalColors.ENDC}"""
        )
        os.system(f"{load_transition_domain_command_string}")

    def run_transfer_script(self, debug_on):
        command_string = "./manage.py transfer_transition_domains_to_domains "

        if debug_on:
            command_string += "--debug "

        proceed_load_transition_domain = TerminalHelper.query_yes_no(
            f"""{TerminalColors.OKCYAN}
            =====================================================
            Running transfer_transition_domains_to_domains script
            =====================================================
            
            {command_string}
            {TerminalColors.FAIL}
            Proceed?
            {TerminalColors.ENDC}"""
        )

        if not proceed_load_transition_domain:
            return
        logger.info(
            f"""{TerminalColors.OKCYAN}
        ==== EXECUTING... ====
        {TerminalColors.ENDC}"""
        )
        os.system(f"{command_string}")

    def run_migration_scripts(self, options):
        file_location = options.get("loaderDirectory") + "/"
        filenames = options.get("loaderFilenames").split()
        if len(filenames) < 3:
            filenames_as_string = "{}".format(", ".join(map(str, filenames)))
            logger.info(
                f"""
            {TerminalColors.FAIL}
            --loaderFilenames expected 3 filenames to follow it,
            but only {len(filenames)} were given:
            {filenames_as_string}

            PLEASE MODIFY THE SCRIPT AND TRY RUNNING IT AGAIN
            ============= TERMINATING =============
            {TerminalColors.ENDC}
            """
            )
            return
        domain_contacts_filename = filenames[0]
        contacts_filename = filenames[1]
        domain_statuses_filename = filenames[2]

        files_are_correct = TerminalHelper.query_yes_no(
            f"""
            {TerminalColors.OKCYAN}
            *** IMPORTANT:  VERIFY THE FOLLOWING ***

            The migration scripts are looking in directory....
            {file_location}

            ....for the following files:
            - domain contacts: {domain_contacts_filename}
            - contacts: {contacts_filename}
            - domain statuses: {domain_statuses_filename}y

            {TerminalColors.FAIL}
            Does this look correct?{TerminalColors.ENDC}"""
        )

        if not files_are_correct:
            # prompt the user to provide correct file inputs
            logger.info(
                f"""
            {TerminalColors.YELLOW}
            PLEASE Re-Run the script with the correct file location and filenames: 
            
            EXAMPLE:
            docker compose run -T app ./manage.py test_domain_migration --runLoaders --loaderDirectory /app/tmp --loaderFilenames escrow_domain_contacts.daily.gov.GOV.txt escrow_contacts.daily.gov.GOV.txt escrow_domain_statuses.daily.gov.GOV.txt
            
            """
            )
            return

        # Get --sep argument
        sep = options.get("sep")

        # Get --resetTable argument
        reset_table = options.get("resetTable")

        # Get --debug argument
        debug_on = options.get("debug")

        # Get --limitParse argument
        debug_max_entries_to_parse = int(
            options.get("limitParse")
        )  # set to 0 to parse all entries

        self.run_load_transition_domain_script(
            file_location,
            domain_contacts_filename,
            contacts_filename,
            domain_statuses_filename,
            sep,
            reset_table,
            debug_on,
            debug_max_entries_to_parse,
        )

        self.run_transfer_script(debug_on)

    def simulate_user_logins(self, debug_on):
        logger.info(
            f"""{TerminalColors.OKCYAN}
                    ==================
                    SIMULATING LOGINS
                    ==================
                    {TerminalColors.ENDC}
                    """
        )
        for invite in DomainInvitation.objects.all():
            # DEBUG:
            TerminalHelper.print_debug(
                debug_on,
                f"""{TerminalColors.OKCYAN}Processing invite: {invite}{TerminalColors.ENDC}""",
            )
            # get a user with this email address
            User = get_user_model()
            try:
                user = User.objects.get(email=invite.email)
                # DEBUG:
                TerminalHelper.print_debug(
                    debug_on,
                    f"""{TerminalColors.OKCYAN}Logging in user: {user}{TerminalColors.ENDC}""",
                )
                Client.force_login(user)
            except User.DoesNotExist:
                # TODO: how should we handle this?
                logger.warn(
                    f"""{TerminalColors.FAIL}No user found {invite.email}{TerminalColors.ENDC}"""
                )

    def handle(
        self,
        **options,
    ):
        """
        Does a diff between the transition_domain and the following tables:
        domain, domain_information and the domain_invitation.

        Produces the following report (printed to the terminal):
            #1 - Print any domains that exist in the transition_domain table
            but not in their corresponding domain, domain information or
            domain invitation tables.
            #2 - Print which table this domain is missing from
            #3- Check for duplicate entries in domain or
            domain_information tables and print which are
            duplicates and in which tables

            (ONLY RUNS with full script option)
            - Emails should be sent to the appropriate users
            note that all moved domains should now be accessible
            on django admin for an analyst

        OPTIONS:
        -- (run all other scripts:
                1 - imports for trans domains
                2 - transfer to domain & domain invitation
                3 - send domain invite)
                ** Triggers table reset **
        """

        # Get --debug argument
        debug_on = options.get("debug")
        # Get --runLoaders argument
        run_loaders_on = options.get("runLoaders")
        # Get --triggerLogins argument
        simulate_user_login_enabled = options.get("triggerLogins")

        prompt_continuation_of_analysis = False

        # Run migration scripts if specified by user...
        if run_loaders_on:
            self.run_migration_scripts(options)
            prompt_continuation_of_analysis = True

        # Simulate user login for each user in domain invitation if sepcified by user
        if simulate_user_login_enabled:
            self.simulate_user_logins(debug_on)
            prompt_continuation_of_analysis = True

        analyze_tables = True
        if prompt_continuation_of_analysis:
            analyze_tables = TerminalHelper.query_yes_no(
                f"""{TerminalColors.FAIL}
                Proceed with table analysis?
                {TerminalColors.ENDC}"""
            )

        # Analyze tables for corrupt data...
        if analyze_tables:
            self.compare_tables(debug_on)
