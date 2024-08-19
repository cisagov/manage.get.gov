import argparse
import logging
import os
import pyzipper
import tablib
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.core.management import BaseCommand
import registrar.admin

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Imports tables from a zip file, exported_tables.zip, containing CSV files in the tmp directory."

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument("--skipEppSave", default=True, action=argparse.BooleanOptionalAction)

    def handle(self, **options):
        """Extracts CSV files from a zip archive and imports them into the respective tables"""

        if settings.IS_PRODUCTION:
            logger.error("import_tables cannot be run in production")
            return

        self.skip_epp_save = options.get("skipEppSave")

        table_names = [
            "User",
            "Contact",
            "Domain",
            "Host",
            "HostIp",
            "DraftDomain",
            "Website",
            "FederalAgency",
            "DomainRequest",
            "DomainInformation",
            "UserDomainRole",
            "PublicContact",
        ]

        # Ensure the tmp directory exists
        os.makedirs("tmp", exist_ok=True)

        # Unzip the file
        zip_filename = "tmp/exported_tables.zip"
        if not os.path.exists(zip_filename):
            logger.error(f"Zip file {zip_filename} does not exist.")
            return

        with pyzipper.AESZipFile(zip_filename, "r") as zipf:
            zipf.extractall("tmp")
            logger.info(f"Extracted zip file {zip_filename} into tmp directory")

        # Import each CSV file
        for table_name in table_names:
            self.import_table(table_name)

    def import_table(self, table_name):
        """Import data from a CSV file into the given table"""

        resourcename = f"{table_name}Resource"

        # Define the directory and the pattern for csv filenames
        tmp_dir = "tmp"
        pattern = f"{table_name}_"

        resourceclass = getattr(registrar.admin, resourcename)
        resource_instance = resourceclass()

        # Find all files that match the pattern
        matching_files = [file for file in os.listdir(tmp_dir) if file.startswith(pattern)]
        for csv_filename in matching_files:
            try:
                with open(f"tmp/{csv_filename}", "r") as csvfile:
                    dataset = tablib.Dataset().load(csvfile.read(), format="csv")
                result = resource_instance.import_data(dataset, dry_run=False, skip_epp_save=self.skip_epp_save)
                if result.has_errors():
                    logger.error(f"Errors occurred while importing {csv_filename}:")
                    for row_error in result.row_errors():
                        row_index = row_error[0]
                        errors = row_error[1]
                        for error in errors:
                            logger.error(f"Row {row_index} - {error.error} - {error.row}")
                else:
                    logger.info(f"Successfully imported {csv_filename} into {table_name}")

            except AttributeError:
                logger.error(f"Resource class {resourcename} not found in registrar.admin")
            except Exception as e:
                logger.error(f"Failed to import {csv_filename}: {e}")
            finally:
                if os.path.exists(csv_filename):
                    os.remove(csv_filename)
                    logger.info(f"Removed temporary file {csv_filename}")

    def clean_table(self, table_name):
        """Delete all rows in the given table"""
        try:
            # Get the model class dynamically
            model = apps.get_model("registrar", table_name)
            # Use a transaction to ensure database integrity
            with transaction.atomic():
                model.objects.all().delete()
            logger.info(f"Successfully cleaned table {table_name}")
        except LookupError:
            logger.error(f"Model for table {table_name} not found.")
        except Exception as e:
            logger.error(f"Error cleaning table {table_name}: {e}")
