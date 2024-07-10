import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import FederalAgency, DomainInformation, Contact


logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    """
    This command uses the PopulateScriptTemplate,
    which provides reusable logging and bulk updating functions for mass-updating fields.
    """

    help = "Loops through each valid User object and updates its verification_type value"
    prompt_title = "Do you wish to update all Senior Officials for Domain Information?"

    def handle(self, domain_info_csv_path, **kwargs):
        """Loops through each valid DomainInformation object and updates its senior official field"""

        # Check if the provided file path is valid.
        if not os.path.isfile(domain_info_csv_path):
            raise argparse.ArgumentTypeError(f"Invalid file path '{domain_info_csv_path}'")

        # Simple check to make sure we don't accidentally pass in the wrong file. Crude but it works.
        if not "information" in domain_info_csv_path.lower():
            raise argparse.ArgumentTypeError(f"Invalid file for domain information: '{domain_info_csv_path}'")

        # Get all ao data.
        ao_dict, ao_ids = self.read_csv_file_and_get_contacts(domain_info_csv_path)
        print(f"aodict: {ao_dict} ao_ids: {ao_ids}")
        contacts = self.get_valid_contacts(ao_ids)

        # Store the ao data we want to recover in a dict of the domain info id,
        # and the value as the actual contact object for faster computation.
        self.domain_ao_dict = {}
        for contact in contacts:
            # Get the 
            domain_info_id = ao_dict[contact.id]
            self.domain_ao_dict[domain_info_id] = contact
        
        print(f"dict is: {self.domain_ao_dict}")

        self.mass_update_records(
            DomainInformation, filter_conditions={"senior_official__isnull": True}, fields_to_update=["senior_official"]
        )
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument("--domain_info_csv_path",  help="A csv containing the domain information id and the contact id")

    def read_csv_file_and_get_contacts(self, file):
        dict_data = {}
        ao_ids = []
        with open(file, "r") as requested_file:
            reader = csv.DictReader(requested_file)
            for row in reader:
                domain_info_id = row["id"]
                ao_id = row["authorizing_official"]
                dict_data[ao_id] = domain_info_id
                ao_ids.append(ao_id)

        return (dict_data, ao_ids)
    
    def get_valid_contacts(self, ao_ids):
        return Contact.objects.filter(id__in=ao_ids)

    def update_record(self, record: DomainInformation):
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
