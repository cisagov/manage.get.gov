import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalHelper, PopulateScriptTemplate
from registrar.models import SeniorOfficial, FederalAgency


logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):

    help = """Populates the initials and fceb fields for FederalAgencies"""

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument("senior_official_csv_path", help="A csv containing information about the SeniorOfficials")

    def handle(self, senior_official_csv_path, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""
        # Check if the provided file path is valid.
        if not os.path.isfile(senior_official_csv_path):
            raise argparse.ArgumentTypeError(f"Invalid file path '{senior_official_csv_path}'")

        self.federal_agency_dict = self.get_agency_dict(senior_official_csv_path)

        filter_condition = {"agency__isnull": False}
        self.mass_update_records(FederalAgency, filter_condition, ["initials", "is_fceb"])

    def update_record(self, record: FederalAgency):
        """Defines how we update the verification_type field"""
        dict_tuple = self.federal_agency_dict.get(record.agency)
        initials, agency_status = dict_tuple

        record.initials = initials
        if agency_status:
            record.is_fceb = True
        else:
            record.is_fceb = False

        message = f"Updating {record} => initials: {initials} | is_fceb: {record.is_fceb}"
        TerminalHelper.colorful_logger("INFO", "OKCYAN", message)
    
    def should_skip_record(self, record) -> bool:
        return record.agency not in self.federal_agency_dict

    def get_agency_dict(self, senior_official_csv_path):
        """Returns a dictionary keyed by the agency name containing initials and agency status"""
        agency_dict = {}
        with open(senior_official_csv_path, "r") as requested_file:
            reader = csv.DictReader(requested_file)
            for row in reader:
                agency_name = row.get("Agency")
                if agency_name:
                    initials = row.get("Initials")
                    agency_status = row.get("Agency Status")
                    agency_dict[agency_name.strip()] = (initials, agency_status)
        
        return agency_dict