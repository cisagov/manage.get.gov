import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalHelper, TerminalColors
from registrar.models import SeniorOfficial, FederalAgency

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """Populates the SeniorOfficial table based off of a given csv"""

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument("federal_cio_csv_path", help="A csv containing information about federal CIOs")

    def handle(self, federal_cio_csv_path, **kwargs):
        """Populates the SeniorOfficial table with data given to it through a CSV"""

        # Check if the provided file path is valid.
        if not os.path.isfile(federal_cio_csv_path):
            raise argparse.ArgumentTypeError(f"Invalid file path '{federal_cio_csv_path}'")

        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            ==Proposed Changes==
            CSV: {federal_cio_csv_path}

            For each item in this CSV, a SeniorOffical record will be added.

            Note: 
                - If the row is missing SO data - it will not be added.
            """,  # noqa: W291
            prompt_title="Do you wish to load records into the SeniorOfficial table?",
        )
        logger.info("Updating...")

        # Get all existing data.
        self.existing_senior_officials = SeniorOfficial.objects.all().prefetch_related("federal_agency")
        self.existing_agencies = FederalAgency.objects.all()

        # Read the CSV
        self.added_senior_officials = []
        self.skipped_rows = []
        with open(federal_cio_csv_path, "r") as requested_file:
            for row in csv.DictReader(requested_file):
                # Note: the csv files we have received do not currently have a phone field.
                # However, we will include it in our kwargs because that is the data we are mapping to
                # and it seems best to check for the data even if it ends up not being there.
                so_kwargs = {
                    "first_name": row.get("First Name"),
                    "last_name": row.get("Last Name"),
                    "title": row.get("Role/Position"),
                    "email": row.get("Email"),
                    "phone": row.get("Phone"),
                }

                # Clean the returned data
                for key, value in so_kwargs.items():
                    if isinstance(value, str):
                        clean_string = value.strip()
                        if clean_string:
                            so_kwargs[key] = clean_string
                        else:
                            so_kwargs[key] = None

                # Handle the federal_agency record seperately (db call)
                agency_name = row.get("Agency").strip() if row.get("Agency") else None
                if agency_name:
                    so_kwargs["federal_agency"] = self.existing_agencies.filter(agency=agency_name).first()

                # Check if at least one field has a non-empty value
                if row and any(so_kwargs.values()):
                    # Split into a function: C901 'Command.handle' is too complex.
                    # Doesn't add it to the DB, but just inits a class of SeniorOfficial.
                    self.create_senior_official(so_kwargs)
                else:
                    self.skipped_rows.append(row)
                    message = f"Skipping row (no data was found): {row}"
                    TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, message)

        # Bulk create the SO fields
        if len(self.added_senior_officials) > 0:
            SeniorOfficial.objects.bulk_create(self.added_senior_officials)

            added_message = f"Added {len(self.added_senior_officials)} records"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKBLUE, added_message)

        if len(self.skipped_rows) > 0:
            skipped_message = f"Skipped {len(self.skipped_rows)} records"
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.MAGENTA, skipped_message)

    def create_senior_official(self, so_kwargs):
        """Creates a senior official object from kwargs but does not add it to the DB"""

        # Create a new SeniorOfficial object
        new_so = SeniorOfficial(**so_kwargs)

        # Store a variable for the console logger
        if all([new_so.first_name, new_so.last_name]):
            record_display = new_so
        else:
            record_display = so_kwargs

        # Before adding this record, check to make sure we aren't adding a duplicate.
        duplicate_field = self.existing_senior_officials.filter(**so_kwargs).exists()
        if not duplicate_field:
            self.added_senior_officials.append(new_so)
            message = f"Creating record: {record_display}"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKCYAN, message)
        else:
            # if this field is a duplicate, don't do anything
            self.skipped_rows.append(new_so)
            message = f"Skipping add on duplicate record: {record_display}"
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, message)
