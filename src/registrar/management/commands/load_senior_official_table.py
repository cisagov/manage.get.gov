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
            If the row is missing a first_name, last_name, or title - it will not be added.
            """,
            prompt_title="Do you wish to load records into the SeniorOfficial table?",
        )
        logger.info("Updating...")

        # Get all existing data.
        existing_senior_officials = SeniorOfficial.objects.all().prefetch_related("federal_agency")
        existing_agencies = FederalAgency.objects.all()

        # Read the CSV
        added_senior_officials, skipped_rows, updated_rows = [], [], []
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

                # Handle the federal_agency record seperately (db call)
                agency_name = row.get("Agency").strip() if row.get("Agency") else None

                # Only first_name, last_name, and title are required
                required_fields = ["first_name", "last_name", "title"]
                if row and all(so_kwargs[field] for field in required_fields):

                    # Get the underlying federal agency record
                    if agency_name:
                        so_kwargs["federal_agency"] = existing_agencies.filter(agency=agency_name).first()

                    # Create a new SeniorOfficial object
                    new_so = SeniorOfficial(**so_kwargs)

                    # Before adding this record, check to make sure we aren't adding a duplicate.
                    existing_field = existing_senior_officials.filter(
                        first_name=so_kwargs.get("first_name"),
                        last_name=so_kwargs.get("last_name"),
                        title=so_kwargs.get("title"),
                    ).first()
                    if not existing_field:
                        added_senior_officials.append(new_so)
                        message = f"Added record: {new_so}"
                        TerminalHelper.colorful_logger("INFO", "OKCYAN", message)
                    else:
                        duplicate_field = existing_senior_officials.filter(**so_kwargs).first()
                        if not duplicate_field:
                            # If we can, just update the row instead
                            for field, value in so_kwargs.items():
                                if getattr(existing_field, field) != value:
                                    setattr(existing_field, field, value)
                            updated_rows.append(existing_field)
                            message = f"Updating record: {existing_field}"
                            TerminalHelper.colorful_logger("INFO", "OKBLUE", message)
                        else:
                            # if this field is a duplicate, don't do anything
                            skipped_rows.append(duplicate_field)
                            message = f"Skipping add on duplicate record: {duplicate_field}"
                            TerminalHelper.colorful_logger("WARNING", "YELLOW", message)
                else:
                    skipped_rows.append(row)
                    message = f"Skipping row (missing first_name, last_name, or title): {row}"
                    TerminalHelper.colorful_logger("WARNING", "YELLOW", message)

        # Bulk create the SO fields
        if len(added_senior_officials) > 0:
            SeniorOfficial.objects.bulk_create(added_senior_officials)

            added_message = f"Added {len(added_senior_officials)} records"
            TerminalHelper.colorful_logger("INFO", "OKGREEN", added_message)

        # Bulk update the SO fields (if any)
        if len(updated_rows) > 0:
            updated_fields = [
                "first_name",
                "last_name",
                "title",
                "email",
                "phone",
                "federal_agency"
            ]
            SeniorOfficial.objects.bulk_update(updated_rows, updated_fields)

            skipped_message = f"Updated {len(updated_rows)} records"
            TerminalHelper.colorful_logger("INFO", "OKBLUE", skipped_message)

        if len(skipped_rows) > 0:
            skipped_message = f"Skipped {len(skipped_rows)} records"
            TerminalHelper.colorful_logger("WARNING", "MAGENTA", skipped_message)
