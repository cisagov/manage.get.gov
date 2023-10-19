import logging
import argparse
import sys

from django_fsm import TransitionNotAllowed  # type: ignore

from django.core.management import BaseCommand

from registrar.models import TransitionDomain
from registrar.models import Domain
from registrar.models import DomainInvitation

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


class Command(BaseCommand):
    help = """ """

    def add_arguments(self, parser):
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse",
            default=0,
            help="Sets max number of entries to load, set to 0 to load all entries",
        )

    def print_debug_mode_statements(
        self, debug_on: bool, debug_max_entries_to_parse: int
    ):
        """Prints additional terminal statements to indicate if --debug
        or --limitParse are in use"""
        self.print_debug(
            debug_on,
            f"""{termColors.OKCYAN}
            ----------DEBUG MODE ON----------
            Detailed print statements activated.
            {termColors.ENDC}
            """,
        )
        self.print_debug(
            debug_max_entries_to_parse > 0,
            f"""{termColors.OKCYAN}
            ----------LIMITER ON----------
            Parsing of entries will be limited to
            {debug_max_entries_to_parse} lines per file.")
            Detailed print statements activated.
            {termColors.ENDC}
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

    
    def handle(
        self,
        **options,
    ):
        """
        Do a diff between the transition_domain and the following tables: 
        domain, domain_information and the domain_invitation. 
        
        It should:
            - Print any domains that exist in the transition_domain table
            but not in their corresponding domain, domain information or
            domain invitation tables.
            - Print which table this domain is missing from
            - Check for duplicate entries in domain or 
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

