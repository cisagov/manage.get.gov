import logging
import argparse
import sys

from django_fsm import TransitionNotAllowed  # type: ignore

from django.core.management import BaseCommand

from registrar.models import TransitionDomain
from registrar.models import Domain
from registrar.models import DomainInvitation
from registrar.models.domain_information import DomainInformation

from registrar.management.commands.utility.terminal_helper import TerminalColors
from registrar.management.commands.utility.terminal_helper import TerminalHelper

from registrar.management.commands.load_transition_domain import Command as load_transition_domain_command

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = """ """

    def add_arguments(self, parser):
        """
        OPTIONAL ARGUMENTS:
        --debug
        A boolean (default to true), which activates additional print statements
        """

        parser.add_argument("--runLoaders",
            help="Runs all scripts (in sequence) for transition domain migrations",
            action=argparse.BooleanOptionalAction)

        # The file arguments have default values for running in the sandbox
        parser.add_argument(
            "--loaderDirectory",
            default="migrationData/",
            help="The location of the files used for load_transition_domain migration script"
        )
        parser.add_argument(
            "domain_contacts_filename",
            default="escrow_domain_contacts.daily.gov.GOV.txt",
            help="Data file with domain contact information"
        )
        parser.add_argument(
            "contacts_filename",
            default="escrow_contacts.daily.gov.GOV.txt",
            help="Data file with contact information",
        )
        parser.add_argument(
            "domain_statuses_filename",
            default="escrow_domain_statuses.daily.gov.GOV.txt",
            help="Data file with domain status information"
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
        self, debug_on: bool
    ):
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

        #TODO: would filteredRelation be faster?
        for transition_domain in TransitionDomain.objects.all():# DEBUG:
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
            matching_domain_informations = DomainInformation.objects.filter(domain__name=transition_domain_name)
            # Check Domain Invitation table
            matching_domain_invitations = DomainInvitation.objects.filter(email=transition_domain_email.lower(), 
                                                                          domain__name=transition_domain_name)

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
        duplicate_domains_as_string = "{}".format(", ".join(map(str, duplicate_domains)))
        missing_domain_informations_as_string = "{}".format(", ".join(map(str, missing_domain_informations)))
        missing_domain_invites_as_string = "{}".format(", ".join(map(str, missing_domain_invites)))
        
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
    
    def run_migration_scripts(self,
                            file_location, 
                            domain_contacts_filename,
                            contacts_filename,
                            domain_statuses_filename):

        files_are_correct = TerminalHelper.query_yes_no(
            f"""
            {TerminalColors.YELLOW}
            PLEASE CHECK: 
            The loader scripts expect to find the following files:
            - domain contacts: {domain_contacts_filename}
            - contacts: {contacts_filename}
            - domain statuses: {domain_statuses_filename}

            The files should be at the following directory;
            {file_location}

            Does this look correct?{TerminalColors.ENDC}"""
        )

        if not files_are_correct:
            # prompt the user to provide correct file inputs
            logger.info(f"""
            {TerminalColors.YELLOW}
            PLEASE Re-Run the script with the correct file location and filenames: 
            EXAMPLE:
            
            
            """)
            return
        load_transition_domain_command.handle(
            domain_contacts_filename,
            contacts_filename,
            domain_statuses_filename
        )

    def handle(
        self,
        # domain_contacts_filename,
        # contacts_filename,
        # domain_statuses_filename,
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

        # Analyze tables for corrupt data...
        self.compare_tables(debug_on)

        # Run migration scripts if specified by user...
        if run_loaders_on:
            file_location = options.get("loaderDirectory")
            # domain_contacts_filename = options.get("domain_contacts_filename")
            # contacts_filename = options.get("contacts_filename")
            # domain_statuses_filename = options.get("domain_statuses_filename")
            # self.run_migration_scripts(file_location, 
            #                            domain_contacts_filename,
            #                            contacts_filename,
            #                            domain_statuses_filename)