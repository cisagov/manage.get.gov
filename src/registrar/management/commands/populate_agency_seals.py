"""Populates Portfolio agency seal field using image with name matching portfolio name."""

import logging
import os
import argparse

from django.core.management import BaseCommand
from registrar.utility.s3_bucket import S3ClientHelper


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Uploads agency seal image(s) to our S3 bucket and populates corresponding Portfolio's "
        "agency seal field."
    )

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument("--directory", default="agency_seals", help="Targeted image directory")
        parser.add_argument(
            "--checkpath",
            default=True,
            help="Flag that determines if we do a check for os.path.exists. Used for test cases",
        )

    def handle(self, agency_seals_dir_path="agency_seals", **options):
        """Grabs the directory then creates current-full.csv in that directory"""

        # Validate provided dir path
        if not os.path.isdir(agency_seals_dir_path):
            raise argparse.ArgumentTypeError(f"Invalid dir path '{agency_seals_dir_path}'")
        
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        check_path = options.get("checkpath")

        logger.info("Generating report...")
        try:
            self.populate_agency_seals(directory, check_path)
        except Exception as err:
            # TODO - #1317: Notify operations when auto report generation fails
            raise err
        else:
            logger.info(f"Successfully uploaded images to S3.")

    def populate_agency_seals(self, directory, check_path):
        """Uploads image to a AWS S3 bucket"""
        s3_client = S3ClientHelper()

        for image_file_name in os.listdir(directory):
            file_path = os.path.join(directory, image_file_name)

            if check_path and not os.path.exists(file_path):
                raise FileNotFoundError(f"Could not find file at '{file_path}'")

            # Upload this generated file for our S3 instance
            try:
                s3_client.upload_file(file_path, image_file_name)
            except Exception as err:
                logger.info(f"Failed to upload uploaded {image_file_name}")
                raise err
            else:
                logger.info(f"Successfully uploaded {image_file_name}")
