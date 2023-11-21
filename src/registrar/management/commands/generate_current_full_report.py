"""Generates current-full.csv and current-federal.csv then uploads them to the desired URL."""
import glob
import logging

import os
import shutil

from django.core.management import BaseCommand

from registrar.management.commands.utility.terminal_helper import TerminalHelper
from registrar.utility import csv_export


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ""

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument("--directory", default="migrationdata", help="Desired directory")

    def handle(self, **options):
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        logger.info("Generating report...")
        self.generate_current_full_report(directory)
        logger.info(f"Success! Created {directory}current-full.csv")

    def generate_current_full_report(self, directory):
        """Creates a current-full.csv file under the migrationdata/ directory"""
        file_path = os.path.join(directory, "current-full.csv")
        with open(file_path, "w") as file:
            csv_export.export_data_full_to_csv(file)
