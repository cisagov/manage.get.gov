"""Data migration: Extends expiration dates for valid domains"""

import argparse
from datetime import date
import logging

from django.core.management import BaseCommand
from registrar.models import Domain
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Extends expiration dates for valid domains"

    # Generates test transition domains for testing send_domain_invitations script.
    # Running this script removes all existing transition domains, so use with caution.
    # Transition domains are created with email addresses provided as command line
    # argument. Email addresses for testing are passed as comma delimited list of
    # email addresses, and are required to be provided. Email addresses from the list
    # are assigned to transition domains at time of creation.

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "--extensionAmount",
            type=int,
            default=1,
            help="Determines the period (in years) to extend expiration dates by",
        )
        parser.add_argument(
            "--parseLimit",
            type=int,
            default=0,
            help="Sets a cap on the number of records to parse",
        )

    def handle(self, **options):
        """"""
        extension_amount = options.get("extensionAmount")
        parse_limit = options.get("parseLimit")

        # Does a check to see if parse_limit is a positive int
        self.check_if_positive_int(parse_limit, "parseLimit")

        # TODO - Do we need to check status?
        valid_domains = Domain.objects.filter(
            expiration_date__gte=date(2023, 11, 15),
            State=Domain.State.READY
        )

        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Extension Amount==
            Period: {extension_amount} year(s)

            ==Proposed Changes==
            Domains to change: {valid_domains.count()}
            """,
            prompt_title="Do you wish to modify Expiration Dates for the given Domains?",
        )

        logger.info(
            f"{TerminalColors.MAGENTA}"
            "Preparing to extend expiration dates..."
            f"{TerminalColors.ENDC}"
        )

        for i, domain in enumerate(valid_domains):
            if i > parse_limit:
                break

            try:
                domain.renew_domain(extension_amount)
            except Exception as err:
                logger.error(
                    f"{TerminalColors.OKBLUE}"
                    f"Failed to update expiration date for {domain}"
                    f"{TerminalColors.ENDC}"
                )
                raise err
            else:
                logger.info(
                    f"{TerminalColors.OKBLUE}"
                    f"Successfully updated expiration date for {domain}"
                    f"{TerminalColors.ENDC}"
                )
    
    def check_if_positive_int(self, value: int, var_name: str):
        """
        Determines if the given integer value is postive or not. 
        If not, it raises an ArgumentTypeError
        """
        if value < 0:
            raise argparse.ArgumentTypeError(
                f"{value} is an invalid integer value for {var_name}. " 
                "Must be positive."
            )

        return value
