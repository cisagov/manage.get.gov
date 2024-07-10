import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import DomainRequest, Contact


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
        if not "request" in domain_request_csv_path.lower():
            raise argparse.ArgumentTypeError(f"Invalid file for domain requests: '{domain_request_csv_path}'")

        # Get all ao data.
        ao_dict, ao_ids = self.read_csv_file_and_get_contacts(domain_request_csv_path)
        contacts = self.get_valid_contacts(ao_ids)

        # Store the ao data we want to recover in a dict of the domain info id,
        # and the value as the actual contact object for faster computation.
        self.domain_ao_dict = {}
        for contact in contacts:
            # Get the
            domain_request_id = ao_dict[contact.id]
            self.domain_ao_dict[domain_request_id] = contact

        self.mass_update_records(
            DomainRequest, filter_conditions={"senior_official__isnull": True}, fields_to_update=["senior_official"]
        )

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "--domain_request_csv_path", help="A csv containing the domain request id and the contact id"
        )

    def read_csv_file_and_get_contacts(self, file):
        dict_data = {}
        ao_ids = []
        with open(file, "r") as requested_file:
            reader = csv.DictReader(requested_file)
            for row in reader:
                domain_request_id = row["id"]
                ao_id = row["authorizing_official"]
                if not row or not domain_request_id or not ao_id:
                    logger.info("Skipping update on row: no data found.")
                    break

                dict_data[ao_id] = domain_request_id
                ao_ids.append(ao_id)

        return (dict_data, ao_ids)

    def get_valid_contacts(self, ao_ids):
        return Contact.objects.filter(id__in=ao_ids)

    def update_record(self, record: DomainRequest):
        """Defines how we update the federal_type field on each record."""
        contact = self.domain_ao_dict.get(record.id)
        record.senior_official = contact
        logger.info(f"{TerminalColors.OKCYAN}Updating {str(record)} => {record.senior_official}{TerminalColors.ENDC}")

    def should_skip_record(self, record) -> bool:  # noqa
        """Defines the conditions in which we should skip updating a record."""
        contact = self.domain_ao_dict.get(record.id)
        # Don't update this record if there isn't ao data to pull from
        if not contact:
            logger.info(
                f"{TerminalColors.YELLOW}Skipping update for {str(record)} => "
                f"Missing authorizing_official data.{TerminalColors.ENDC}"
            )
            return True
        else:
            return False
