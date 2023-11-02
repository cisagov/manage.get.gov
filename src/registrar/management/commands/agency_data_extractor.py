import argparse
import csv
import logging

from django.core.management import BaseCommand

from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)
from registrar.models.domain_application import DomainApplication

logger = logging.getLogger(__name__)

# DEV SHORTCUT:
# Example command for running this script:
# docker compose run -T app ./manage.py agency_data_extractor 20231009.agency.adhoc.dotgov.txt --dir /app/tmp --debug

class Command(BaseCommand):
    help = """Loads data for domains that are in transition
    (populates transition_domain model objects)."""

    def add_arguments(self, parser):
        """Add file that contains agency data"""
        parser.add_argument(
            "agency_data_filename", help="Data file with agency information"
        )
        parser.add_argument(
            "--dir", default="migrationdata", help="Desired directory"
        )
        parser.add_argument("--sep", default="|", help="Delimiter character")

        parser.add_argument("--debug", help="Prints additional debug statements to the terminal", action=argparse.BooleanOptionalAction)

    def extract_agencies(
        self, 
        agency_data_filepath: str, 
        sep: str,
        debug: bool
    ) -> [str]:
        """Extracts all the agency names from the provided agency file"""
        agency_names = []
        logger.info(f"{TerminalColors.OKCYAN}Reading agency data file {agency_data_filepath}{TerminalColors.ENDC}")
        with open(agency_data_filepath, "r") as agency_data_filepath:  # noqa
            for row in csv.reader(agency_data_filepath, delimiter=sep):
                agency_name = row[1]
                TerminalHelper.print_conditional(debug, f"Checking: {agency_name}")
                agency_names.append(agency_name)
        logger.info(f"{TerminalColors.OKCYAN}Checked {len(agency_names)} agencies{TerminalColors.ENDC}")
        return agency_names
    
    def compare_lists(self, new_agency_list: [str], current_agency_list: [str], debug: bool):
        """
        Compares the new agency list with the current
        agency list and provides the equivalent of
        an outer-join on the two (printed to the terminal)
        """

        new_agencies = []
        # 1 - Get all new agencies that we don't already have (We might want to ADD these to our list)
        for agency in new_agency_list:
            if agency not in current_agency_list:
                new_agencies.append(agency)
                TerminalHelper.print_conditional(debug, f"{TerminalColors.YELLOW}Found new agency: {agency}{TerminalColors.ENDC}")

        possibly_unused_agencies = []
        # 2 - Get all new agencies that we don't already have (We might want to ADD these to our list)
        for agency in current_agency_list:
            if agency not in new_agency_list:
                possibly_unused_agencies.append(agency)
                TerminalHelper.print_conditional(debug, f"{TerminalColors.YELLOW}Possibly unused agency detected: {agency}{TerminalColors.ENDC}")

        # Print the summary of findings
        # 1 - Print the list of agencies in the NEW list, which we do not already have
        # 2 - Print the list of agencies that we currently have, which are NOT in the new list (these might be eligible for removal?) TODO: would we ever want to remove existing agencies?
        new_agencies_as_string = "{}".format(
            ",\n        ".join(map(str, new_agencies))
        )
        possibly_unused_agencies_as_string = "{}".format(
            ",\n        ".join(map(str, possibly_unused_agencies))
        )

        logger.info(f"""
        {TerminalColors.OKGREEN}
        ======================== SUMMARY OF FINDINGS ============================
        {len(new_agency_list)} AGENCIES WERE PROVIDED in the agency file.
        {len(current_agency_list)} AGENCIES ARE CURRENTLY IN OUR SYSTEM.

        {len(new_agency_list)-len(new_agencies)} AGENCIES MATCHED
        (These are agencies that are in the given agency file AND in our system already)
        
        {len(new_agencies)} AGENCIES TO ADD:
        These agencies were in the provided agency file, but are not in our system.
        {TerminalColors.YELLOW}{new_agencies_as_string}
        {TerminalColors.OKGREEN}

        {len(possibly_unused_agencies)} AGENCIES TO (POSSIBLY) REMOVE:
        These agencies are in our system, but not in the provided agency file:
        {TerminalColors.YELLOW}{possibly_unused_agencies_as_string}
        {TerminalColors.ENDC}
        """)

    def handle(
        self,
        agency_data_filename,
        **options,
    ):
        """Parse the agency data file."""

        # Get all the arguments
        sep = options.get("sep")
        debug = options.get("debug")
        dir = options.get("dir")

        agency_data_file = dir+"/"+agency_data_filename

        new_agencies = self.extract_agencies(agency_data_file, sep, debug)
        existing_agencies = DomainApplication.AGENCIES
        self.compare_lists(new_agencies, existing_agencies, debug)