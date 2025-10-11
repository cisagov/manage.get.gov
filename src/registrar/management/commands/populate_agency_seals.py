"""Populates Portfolio agency seal field using image with name matching portfolio name."""

import logging
import os
import argparse

from django.core.management import BaseCommand
from registrar.utility.s3_bucket import S3ClientHelper
from registrar.models import Portfolio
from django.db.models.functions import Trim


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Uploads agency seal image(s) to our S3 bucket and populates corresponding Portfolio's "
        "agency seal field."
    )

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument(
            "--directory", 
            default="registrar/assets/img/agency_seals", 
            help="Targeted image directory"
        )
        parser.add_argument(
            "--checkpath",
            default=True,
            help="Flag that determines if we do a check for os.path.exists. Used for test cases",
        )

    def handle(self, agency_seals_dir_path="registrar/assets/img/agency_seals", **options):
        """Uploads agency seals to S3 bucket and populates corresponding portfolio's
        agency seal field."""

        # Validate provided dir path
        if not os.path.isdir(agency_seals_dir_path):
            raise argparse.ArgumentTypeError(f"Invalid dir path '{agency_seals_dir_path}'")
        
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        check_path = options.get("checkpath")

        logger.info("Processing agency seals in {agency_seals_dir_path}...")
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

            try:
                # Upload this generated file for our S3 instance
                # s3_client.upload_file(file_path, image_file_name)

                # Search for a matching portfolio agency with the same agency name
                portfolio = self.search_matching_portfolio(image_file_name)
                if portfolio is None:
                    logger.info(f"Could not find matching portfolio for agency seal {image_file_name}")
            except Exception as err:
                logger.info(f"Failed to upload {image_file_name}.")
                raise err
            else:
                logger.info(f"Successfully uploaded {image_file_name}.")

            # Download agency seal from S3 and assign it to matching portfolio
            try:
                portfolio = self.search_matching_portfolio(image_file_name)
                if portfolio:
                    # file = s3_client.get_file(image_file_name, decode_to_utf=False)
                    # portfolio.agency_seal = file
                    portfolio.agency_seal.name = "Department_of_Veterans_Affairs_seal.png"
                    portfolio.save()
                    print("portfolio agency seal: ", portfolio.agency_seal.__dict__)
                else:
                    logger.info(f"Could not find matching portfolio for agency seal {image_file_name}")
            except Exception as err:
                logger.info(f"Failed to download {image_file_name} from S3.")
                raise err


    def search_matching_portfolio(self, image_file_name):
        """Given an image file name, search if a Portfolio with the same
        federal agency name exists and return if one exists."""
        # Extract agency name from image filename
        # remove seal.png
        image_file_agency = image_file_name.replace("_seal.png", "").replace("_", " ")
        logger.info(f"Searching for portfolio with agency seal for {image_file_agency}")

        # Annotate Portfolios with name removing whitespace 
        matching_portfolio = Portfolio.objects.filter(organization_name=image_file_agency).first()
        return matching_portfolio
