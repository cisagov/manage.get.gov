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
            info_to_inspect=f"""
            ==Proposed Changes==
            CSV: {federal_cio_csv_path}

            For each item in this CSV, a SeniorOffical record will be added.

            Note: 
            If the row is SO data - it will not be added.
            """,
            prompt_title="Do you wish to load records into the SeniorOfficial table?",
        )
        logger.info("Updating...")

        # Get all existing data.
        existing_senior_officials = SeniorOfficial.objects.all().prefetch_related("federal_agency")
        existing_agencies = FederalAgency.objects.all()

        # Read the CSV
        added_senior_officials, skipped_rows = [], []
        with open(federal_cio_csv_path, "r") as requested_file:
            for row in csv.DictReader(requested_file):
                # Note: the csv doesn't have a phone field, but we can try to pull one anyway.
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
                        so_kwargs[key] = value.strip()

                # Handle the federal_agency record seperately (db call)
                agency_name = row.get("Agency").strip() if row.get("Agency") else None
                if agency_name:
                    so_kwargs["federal_agency"] = existing_agencies.filter(agency=agency_name).first()

                # Check if at least one field has a non-empty value
                if row and any(so_kwargs.values()):
                    
                    # WORKAROUND: Placeholder value for first name,
                    # as not having these makes it impossible to access through DJA.
                    old_first_name = so_kwargs["first_name"]
                    if not so_kwargs["first_name"]:
                        so_kwargs["first_name"] = "-"

                    # Create a new SeniorOfficial object
                    new_so = SeniorOfficial(**so_kwargs)

                    # Store a variable for the console logger
                    if any([old_first_name, new_so.last_name]):
                        record_display = new_so
                    else:
                        record_display = so_kwargs

                    # Before adding this record, check to make sure we aren't adding a duplicate.
                    duplicate_field = existing_senior_officials.filter(**so_kwargs).exists()
                    if not duplicate_field:
                        added_senior_officials.append(new_so)
                        message = f"Creating record: {record_display}"
                        TerminalHelper.colorful_logger("INFO", "OKCYAN", message)
                    else:
                        # if this field is a duplicate, don't do anything
                        skipped_rows.append(row)
                        message = f"Skipping add on duplicate record: {record_display}"
                        TerminalHelper.colorful_logger("WARNING", "YELLOW", message)
                else:
                    skipped_rows.append(row)
                    message = f"Skipping row (no data was found): {row}"
                    TerminalHelper.colorful_logger("WARNING", "YELLOW", message)

        # Bulk create the SO fields
        if len(added_senior_officials) > 0:
            SeniorOfficial.objects.bulk_create(added_senior_officials)

            added_message = f"Added {len(added_senior_officials)} records"
            TerminalHelper.colorful_logger("INFO", "OKGREEN", added_message)

        if len(skipped_rows) > 0:
            skipped_message = f"Skipped {len(skipped_rows)} records"
            TerminalHelper.colorful_logger("WARNING", "MAGENTA", skipped_message)
