"""Generates current-full.csv and current-federal.csv then uploads them to the desired URL."""
import logging
import os

from django.core.management import BaseCommand
from registrar.utility import csv_export
from registrar.utility.s3_bucket import S3ClientHelper


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
        """Grabs the directory then creates current-full.csv in that directory"""
        file_name = "current-full.csv"
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        check_path = options.get("checkpath")
        logger.info("Generating report...")

        self.generate_current_full_report(directory, file_name, check_path)

        file_path = os.path.join(directory, file_name)
        logger.info(f"Success! Created {file_path}")

    def generate_current_full_report(self, directory, file_name, check_path):
        """Creates a current-full.csv file under the specified directory"""
        s3_client = S3ClientHelper()
        # TODO - #1403, push to the S3 instance instead
        file_path = os.path.join(directory, file_name)
        # TODO - Don't genererate a useless file
        with open(file_path, "w") as file:
            csv_export.export_data_full_to_csv(file)

        if check_path and not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find newly created file at '{file_path}'")
        
        s3_client.upload_file(file_path, file_name)
