"""Populates Portfolio agency seal field using image with name matching portfolio name."""

import logging
import os
import argparse

from django.core.management import BaseCommand
from registrar.models import Portfolio
from typing import List


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Uploads agency seal image(s) to our S3 bucket and populates corresponding Portfolio's "
        "agency seal field."
    )

    def __init__(self):
        super().__init__()
        self.portfolios_with_updated_seals: List[Portfolio] = []
        self.unmatched_seals: list[str] = []

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument(
            "--directory", 
            default="registrar/assets/img/registrar/agency_seals", 
            help="Targeted image directory"
        )
        parser.add_argument(
            "--checkpath",
            default=True,
            help="Flag that determines if we do a check for os.path.exists. Used for test cases",
        )

    def handle(self, agency_seals_dir_path="registrar/assets/img/registrar/agency_seals", **options):
        """Process all images in agency seals folder and assign to corresponding portfolio's
        agency seal field."""

        # Validate provided dir path
        if not os.path.isdir(agency_seals_dir_path):
            raise argparse.ArgumentTypeError(f"Invalid dir path '{agency_seals_dir_path}'")
        
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        check_path = options.get("checkpath")

        logger.info("Reading agency seals in {agency_seals_dir_path}...")
        try:
            self.populate_agency_seals(directory, check_path)
        except Exception as err:
            raise err
        else:
            if len(self.portfolios_with_updated_seals) > 0:
                logger.info(
                    f"Successfully assigned agency seal images to {len(self.portfolios_with_updated_seals)} portfolios: {', '.join(map(str, self.portfolios_with_updated_seals))}"
                )
            if len(self.unmatched_seals) > 0:
                logger.info(
                    f"Failed to assign {len(self.unmatched_seals)} images in {agency_seals_dir_path}: {', '.join(self.unmatched_seals)}."
                )

    def populate_agency_seals(self, directory, check_path):
        """Assign agency seal image to portfolio with matching organization name."""

        for image_file_name in os.listdir(directory):
            file_path = os.path.join(directory, image_file_name)

            if check_path and not os.path.exists(file_path):
                raise FileNotFoundError(f"Could not find file at '{file_path}'")

            # Download agency seal from S3 and assign it to matching portfolio
            try:
                portfolio = self.search_matching_portfolio(image_file_name)
                if portfolio:
                    portfolio.agency_seal.name = image_file_name
                    portfolio.save()
                    self.portfolios_with_updated_seals.append(portfolio)
                    logger.info(f"Successfully assigned {portfolio} agency seal to image {image_file_name}.")
                else:
                    self.unmatched_seals.append(image_file_name)
                    logger.info(f"Could not find portfolio matching agency name for {image_file_name}.")
            except Exception as err:
                logger.info(f"Failed to process image {image_file_name}.")
                raise err

    def search_matching_portfolio(self, image_file_name):
        """Given an image file name, search if a Portfolio with the same
        federal agency name exists and return if one exists."""
        # Extract agency name from image filename
        image_file_agency = image_file_name[:image_file_name.rindex('_')]
        image_file_agency = image_file_agency.replace("_", " ")
        logger.info(f"Searching for portfolio with agency seal for {image_file_agency}")

        # Annotate Portfolios with name removing whitespace 
        matching_portfolio = Portfolio.objects.filter(organization_name__iexact=image_file_agency).first()
        return matching_portfolio
