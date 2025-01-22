import argparse
import logging

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from registrar.models import Portfolio  
from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)
logger = logging.getLogger(__name__)

ALLOWED_PORTFOLIOS = [
    "Department of Veterans Affairs",
    "Department of the Treasury",
    "National Archives and Records Administration",
    "Department of Defense",
    "Department of Defense",
    "Office of Personnel Management",
    "National Aeronautics and Space Administration",
    "City and County of San Francisco",
    "State of Arizona, Executive Branch",
    "State of Arizona, Executive Branch",
    "Department of the Interior",
    "Department of State",
    "Department of Justice",
    "Department of Veterans Affairs",
    "Capitol Police",
    "Administrative Office of the Courts",
    "Supreme Court of the United States",
]

class Command(BaseCommand):
    help = 'Remove all Portfolio entries with names not in the allowed list.'


    def add_arguments(self, parser):
        """
        OPTIONAL ARGUMENTS:
        --debug
        A boolean (default to true), which activates additional print statements
        """
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)


    def prompt_delete_entries(self, portfolios_to_delete, debug_on):
        """Brings up a prompt in the terminal asking
        if the user wishes to delete data in the
        Portfolio table.  If the user confirms,
        deletes the data in the Portfolio table"""

        entries_to_remove_by_name = list(portfolios_to_delete.values_list("organization_name", flat=True))
        formatted_entries = "\n\t\t".join(entries_to_remove_by_name)
        confirm_delete = TerminalHelper.query_yes_no(
            f"""
            {TerminalColors.FAIL}
            WARNING: You are about to delete the following portfolios:

                {formatted_entries}

            Are you sure you want to continue?{TerminalColors.ENDC}"""
        )
        if confirm_delete:
            logger.info(
                f"""{TerminalColors.YELLOW}
            ----------Deleting entries----------
            (please wait)
            {TerminalColors.ENDC}"""
            )
            self.delete_entries(portfolios_to_delete, debug_on)
        else:
            logger.info(
            f"""{TerminalColors.OKCYAN}
            ----------No entries deleted----------
            (exiting script)
            {TerminalColors.ENDC}"""
            )



    def delete_entries(self, portfolios_to_delete, debug_on):
        # Log the number of entries being removed
        count = portfolios_to_delete.count()
        if count == 0:
            logger.info(
                f"""{TerminalColors.OKCYAN}
                No entries to remove.
                {TerminalColors.ENDC}
                """
            )
            return

        # If debug mode is on, print out entries being removed
        if debug_on:
            entries_to_remove_by_name = list(portfolios_to_delete.values_list("organization_name", flat=True))
            formatted_entries = ", ".join(entries_to_remove_by_name)
            logger.info(
                f"""{TerminalColors.YELLOW}
                Entries to be removed: {formatted_entries}
                {TerminalColors.ENDC}
                """
            )

        # Delete the entries
        try:
            portfolios_to_delete.delete()
            # Output a success message
            logger.info(
                f"""{TerminalColors.OKGREEN}
                Successfully removed {count} entries.
                {TerminalColors.ENDC}
                """
            )
        except IntegrityError as e:
            logger.info(
                f"""{TerminalColors.FAIL}
                Could not delete some entries due to protected relationships
                {TerminalColors.ENDC}
                """
            )




    def handle(self, *args, **options):
        # Get all Portfolio entries not in the allowed portfolios list
        portfolios_to_delete = Portfolio.objects.exclude(organization_name__in=ALLOWED_PORTFOLIOS)

        self.prompt_delete_entries(portfolios_to_delete, options.get("debug"))
