import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import DomainRequest

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    """
    This command uses the PopulateScriptTemplate,
    which provides reusable logging and bulk updating functions for mass-updating fields.
    """

    help = """Loops through each valid DomainRequest object and updates its senior official field"""
    prompt_title = "Do you wish to update all Senior Officials for Domain Requests?"

    def handle(self, domain_request_csv_path, **kwargs):
        """Loops through each valid DomainRequest object and updates its senior official field"""

        # Check if the provided file path is valid.
        if not os.path.isfile(domain_request_csv_path):
            raise argparse.ArgumentTypeError(f"Invalid file path '{domain_request_csv_path}'")

        # Simple check to make sure we don't accidentally pass in the wrong file. Crude but it works.
        if "request" not in domain_request_csv_path.lower():
            raise argparse.ArgumentTypeError(f"Invalid file for domain requests: '{domain_request_csv_path}'")

        # Get all ao data.
        self.ao_dict = {}
        self.ao_dict = self.read_csv_file_and_get_contacts(domain_request_csv_path)

        self.mass_update_records(
            DomainRequest,
            filter_conditions={
                "senior_official__isnull": True,
            },
            fields_to_update=["senior_official"],
        )

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "--domain_request_csv_path", help="A csv containing the domain request id and the contact id"
        )

    def read_csv_file_and_get_contacts(self, file):
        dict_data: dict = {}
        with open(file, "r") as requested_file:
            reader = csv.DictReader(requested_file)
            for row in reader:
                domain_request_id = row.get("id")
                ao_id = row.get("authorizing_official")
                if ao_id:
                    ao_id = int(ao_id)
                if domain_request_id and ao_id:
                    dict_data[int(domain_request_id)] = ao_id

        return dict_data

    def update_record(self, record: DomainRequest):
        """Defines how we update the federal_type field on each record."""
        record.senior_official_id = self.ao_dict.get(record.id)
        # record.senior_official = Contact.objects.get(id=contact_id)
        logger.info(f"{TerminalColors.OKCYAN}Updating {str(record)} => {record.senior_official}{TerminalColors.ENDC}")

    def should_skip_record(self, record) -> bool:  # noqa
        """Defines the conditions in which we should skip updating a record."""
        # Don't update this record if there isn't ao data to pull from
        if self.ao_dict.get(record.id) is None:
            logger.info(
                f"{TerminalColors.YELLOW}Skipping update for {str(record)} => "
                f"Missing authorizing_official data.{TerminalColors.ENDC}"
            )
            return True
        else:
            return False
