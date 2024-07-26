import argparse
import csv
import logging
import os
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import SeniorOfficial, FederalAgency


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """Populates the SeniorOfficial table based off of a given csv"""

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "senior_official_csv_path", help="A csv containing information about the SeniorOfficials"
        )

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

            existing_senior_officials = SeniorOfficial.objects.all()
            print(f"first: {FederalAgency.objects.first()}")
            for row in reader:
                first_name = row.get("First Name")
                last_name = row.get("Last Name")
                title = row.get("Role/Position")
                required_fields = [
                    first_name,
                    last_name,
                    title
                ]
                if row and not None in required_fields and not "" in required_fields:
                    # Missing phone?
                    # phone
                    agency = FederalAgency.objects.filter(agency=row.get("agency")).first()
                    r = row.get("agency")
                    print(f"agency: {agency} vs r: {r}")
                    so_kwargs = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "title": title,
                        "email": row.get("Email"),
                        "federal_agency": agency,
                    }

                    new_so = SeniorOfficial(
                        **so_kwargs
                    )

                    is_duplicate = existing_senior_officials.filter(
                        first_name=new_so.first_name, last_name=new_so.last_name, title=new_so.title,
                        email=new_so.email, federal_agency=new_so.federal_agency
                    ).exists()
                    if not is_duplicate:
                        added_senior_officials.append(new_so)
                        logger.info(f"Added record: {new_so}")
                    else:
                        logger.info(f"Skipping add on duplicate record {new_so}")
                else:
                    skipped_rows.append(row)
                    logger.info(f"Skipping row: {row}")

        logger.info(f"Added list: {added_senior_officials}")
        logger.info(f"Skipped list: {skipped_rows}")
        logger.info(f"Added {len(added_senior_officials)} records")
        logger.info(f"Skipped {len(skipped_rows)} records")
        SeniorOfficial.objects.bulk_create(added_senior_officials)
