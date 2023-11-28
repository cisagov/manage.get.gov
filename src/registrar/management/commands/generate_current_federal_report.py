"""Generates current-full.csv and current-federal.csv then uploads them to the desired URL."""
import logging
import os

from django.core.management import BaseCommand
from registrar.utility import csv_export


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ""

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument("--directory", default="migrationdata", help="Desired directory")
        parser.add_argument(
            "--checkpath",
            default=True,
            help="Flag that determines if we do a check for os.path.exists. Used for test cases",
        )

    def handle(self, **options):
        """Grabs the directory then creates current-federal.csv in that directory"""
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        check_path = options.get("checkpath")
        logger.info("Generating report...")

        self.generate_current_federal_report(directory, check_path)
        logger.info(f"Success! Created {directory}current-federal.csv")

    def generate_current_federal_report(self, directory, check_path):
        """Creates a current-full.csv file under the specified directory"""
        # TODO - #1403, push to the S3 instance instead
        file_path = os.path.join(directory, "current-federal.csv")
        with open(file_path, "w") as file:
            csv_export.export_data_federal_to_csv(file)

        if check_path and not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find newly created file at '{file_path}'")
