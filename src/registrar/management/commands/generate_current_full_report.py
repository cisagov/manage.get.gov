"""Generates current-full.csv and current-federal.csv then uploads them to the desired URL."""

import logging
import os

from django.core.management import BaseCommand
from registrar.utility import csv_export
from registrar.utility.s3_bucket import S3ClientHelper


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Generates and uploads a current-full.csv file to our S3 bucket " "which is based off of all existing Domains."
    )

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
        try:
            self.generate_current_full_report(directory, file_name, check_path)
        except Exception as err:
            # TODO - #1317: Notify operations when auto report generation fails
            raise err
        else:
            logger.info(f"Success! Created {file_name}")

    def generate_current_full_report(self, directory, file_name, check_path):
        """Creates a current-full.csv file under the specified directory,
        then uploads it to a AWS S3 bucket"""
        s3_client = S3ClientHelper()
        file_path = os.path.join(directory, file_name)

        # Generate a file locally for upload
        with open(file_path, "w") as file:
            csv_export.DomainDataFull.export_data_to_csv(file)

        if check_path and not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find newly created file at '{file_path}'")

        # Upload this generated file for our S3 instance
        # s3_client.upload_file(file_path, file_name)
