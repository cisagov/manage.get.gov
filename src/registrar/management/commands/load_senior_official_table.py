import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalHelper
from registrar.models import SeniorOfficial, FederalAgency


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """Populates the SeniorOfficial table based off of a given csv"""

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument("senior_official_csv_path", help="A csv containing information about the SeniorOfficials")

    def handle(self, senior_official_csv_path, **kwargs):
        """Loops through each valid DomainRequest object and updates its senior official field"""

        # Check if the provided file path is valid.
        if not os.path.isfile(senior_official_csv_path):
            raise argparse.ArgumentTypeError(f"Invalid file path '{senior_official_csv_path}'")

        # Get all ao data.
        added_senior_officials = []
        skipped_rows = []
        with open(senior_official_csv_path, "r") as requested_file:
            reader = csv.DictReader(requested_file)

            existing_senior_officials = SeniorOfficial.objects.all().prefetch_related("federal_agency")
            existing_fed_agencies = FederalAgency.objects.all()
            for row in reader:

                # Note: the csv doesn't have a phone field, but we can try to pull one anyway.
                so_kwargs = {
                    "first_name": row.get("First Name"),
                    "last_name": row.get("Last Name"),
                    "title": row.get("Role/Position"),
                    "email": row.get("Email"),
                    "phone": row.get("Phone"),
                }

                # Only first_name, last_name, and title are required
                required_fields = ["first_name", "last_name", "title"]
                if row and all(so_kwargs[field] for field in required_fields):
                    _agency = row.get("Agency")
                    if _agency:
                        _federal_agency = existing_fed_agencies.filter(agency=_agency.strip()).first()
                        so_kwargs["federal_agency"] = _federal_agency

                    new_so = SeniorOfficial(**so_kwargs)

                    # Before adding this record, check to make sure we aren't adding a duplicate.
                    is_duplicate = existing_senior_officials.filter(
                        # Check on every field that we're adding
                        **{key: value for key, value in so_kwargs.items()}
                    ).exists()
                    if not is_duplicate:
                        added_senior_officials.append(new_so)
                        message = f"Added record: {new_so}"
                        TerminalHelper.colorful_logger("INFO", "OKCYAN", message)
                    else:
                        skipped_rows.append(new_so)
                        message = f"Skipping add on duplicate record: {new_so}"
                        TerminalHelper.colorful_logger("WARNING", "YELLOW", message)
                else:
                    skipped_rows.append(row)
                    message = f"Skipping row: {row}"
                    TerminalHelper.colorful_logger("WARNING", "YELLOW", message)

        added_message = f"Added {len(added_senior_officials)} records"
        TerminalHelper.colorful_logger("INFO", "OKGREEN", added_message)

        if len(skipped_rows) > 0:
            skipped_message = f"Skipped {len(skipped_rows)} records"
            TerminalHelper.colorful_logger("WARNING", "MAGENTA", skipped_message)

        SeniorOfficial.objects.bulk_create(added_senior_officials)
