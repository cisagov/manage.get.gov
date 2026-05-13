import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalHelper, PopulateScriptTemplate, TerminalColors
from registrar.models import FederalAgency

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):

    help = """Populates the initials and fceb fields for FederalAgencies"""

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument("federal_cio_csv_path", help="A csv containing information about federal CIOs")

    def handle(self, federal_cio_csv_path, **kwargs):
        """Loops through each FederalAgency object and attempts to update is_fceb and initials"""

        # Check if the provided file path is valid.
        if not os.path.isfile(federal_cio_csv_path):
            raise argparse.ArgumentTypeError(f"Invalid file path '{federal_cio_csv_path}'")

        # Returns a dictionary keyed by the agency name containing initials and agency status
        self.federal_agency_dict = {}
        with open(federal_cio_csv_path, "r") as requested_file:
            for row in csv.DictReader(requested_file):
                agency_name = row.get("Agency")
                if agency_name:
                    initials = row.get("Initials")
                    agency_status = row.get("Agency Status")
                    self.federal_agency_dict[agency_name.strip()] = (initials, agency_status)

        # Update every federal agency record
        self.mass_update_records(FederalAgency, {"agency__isnull": False}, ["acronym", "is_fceb"])

    def update_record(self, record: FederalAgency):
        """For each record, update the initials and is_fceb field if data exists for it"""
        initials, agency_status = self.federal_agency_dict.get(record.agency)

        record.acronym = initials
        if agency_status and isinstance(agency_status, str) and agency_status.strip().upper() == "FCEB":
            record.is_fceb = True
        else:
            record.is_fceb = False

        message = f"Updating {record} => initials: {initials} | is_fceb: {record.is_fceb}"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKCYAN, message)

    def should_skip_record(self, record) -> bool:
        """Skip record update if there is no data for that particular agency"""
        return record.agency not in self.federal_agency_dict
