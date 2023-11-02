import argparse
import csv
import logging

from django.core.management import BaseCommand

from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)
from registrar.models.domain_application import DomainApplication
from registrar.models.transition_domain import TransitionDomain

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

    @staticmethod
    def extract_agencies(
        agency_data_filepath: str, 
        sep: str,
        debug: bool
    ) -> [str]:
        """Extracts all the agency names from the provided 
        agency file (skips any duplicates) and returns those
        names in an array"""
        agency_names = []
        logger.info(f"{TerminalColors.OKCYAN}Reading agency data file {agency_data_filepath}{TerminalColors.ENDC}")
        with open(agency_data_filepath, "r") as agency_data_filepath:  # noqa
            for row in csv.reader(agency_data_filepath, delimiter=sep):
                agency_name = row[1]
                TerminalHelper.print_conditional(debug, f"Checking: {agency_name}")
                if agency_name not in agency_names:
                    agency_names.append(agency_name)
        logger.info(f"{TerminalColors.OKCYAN}Checked {len(agency_names)} agencies{TerminalColors.ENDC}")
        return agency_names
    
    @staticmethod
    def compare_agency_lists(provided_agencies: [str],
                      existing_agencies: [str],
                      debug: bool):
        """
        Compares new_agencies with existing_agencies and 
        provides the equivalent of an outer-join on the two
        (printed to the terminal)
        """

        new_agencies = []
        # 1 - Get all new agencies that we don't already have (We might want to ADD these to our list)
        for agency in provided_agencies:
            if agency not in existing_agencies and agency not in new_agencies:
                new_agencies.append(agency)
                TerminalHelper.print_conditional(debug, f"{TerminalColors.YELLOW}Found new agency: {agency}{TerminalColors.ENDC}")

        possibly_unused_agencies = []
        # 2 - Get all new agencies that we don't already have (We might want to ADD these to our list)
        for agency in existing_agencies:
            if agency not in provided_agencies and agency not in possibly_unused_agencies:
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
        {len(provided_agencies)} AGENCIES WERE PROVIDED in the agency file.
        {len(existing_agencies)} AGENCIES FOUND IN THE TARGETED SYSTEM.

        {len(provided_agencies)-len(new_agencies)} AGENCIES MATCHED
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
        
    @staticmethod
    def print_agency_list(agencies):
        full_agency_list_as_string = "{}".format(
            ",\n".join(map(str, agencies))
        )
        logger.info(
            f"\n{TerminalColors.YELLOW}"
            f"\n{full_agency_list_as_string}"
            f"{TerminalColors.OKGREEN}"
        )

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
        hard_coded_agencies = DomainApplication.AGENCIES
        transition_domain_agencies = TransitionDomain.objects.all().values_list('federal_agency')
        print(transition_domain_agencies)

        # OPTION to compare the agency file to our hard-coded list
        print_full_list = TerminalHelper.query_yes_no(f"{TerminalColors.FAIL}Would you like to check {agency_data_filename} against our hard-coded list of agencies?{TerminalColors.ENDC}")
        if print_full_list:
            self.compare_agency_lists(new_agencies, hard_coded_agencies, debug)
        
        # OPTION to compare the agency file to Transition Domains
        print_full_list = TerminalHelper.query_yes_no(f"{TerminalColors.FAIL}Would you like to check {agency_data_filename} against Transition Domain contents?{TerminalColors.ENDC}")
        if print_full_list:
            self.compare_agency_lists(new_agencies, transition_domain_agencies, debug)

        # OPTION to print out the full list of agencies from the agency file
        print_full_list = TerminalHelper.query_yes_no(f"{TerminalColors.FAIL}Would you like to print the full list of agencies from the given agency file?{TerminalColors.ENDC}")
        if print_full_list:
            logger.info(
            f"\n{TerminalColors.OKGREEN}"
            f"\n======================== FULL LIST OF IMPORTED AGENCIES ============================"
            f"\nThese are all the agencies provided by the given agency file."
            )
            self.print_agency_list(new_agencies)