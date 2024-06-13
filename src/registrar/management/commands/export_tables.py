import logging
import os
import pyzipper
from django.core.management import BaseCommand
import registrar.admin

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Exports tables in csv format to zip file in tmp directory."

    def handle(self, **options):
        """Generates CSV files for specified tables and creates a zip archive"""
        table_names = [
            "User",
            "Contact",
            "Domain",
            "DomainRequest",
            "DomainInformation",
            "FederalAgency",
            "UserDomainRole",
            "DraftDomain",
            "Website",
            "HostIp",
            "Host",
            "PublicContact",
        ]

        # Ensure the tmp directory exists
        os.makedirs("tmp", exist_ok=True)

        for table_name in table_names:
            self.export_table(table_name)

        # Create a zip file containing all the CSV files
        zip_filename = "tmp/exported_tables.zip"
        with pyzipper.AESZipFile(zip_filename, "w", compression=pyzipper.ZIP_DEFLATED) as zipf:
            for table_name in table_names:
                csv_filename = f"tmp/{table_name}.csv"
                if os.path.exists(csv_filename):
                    zipf.write(csv_filename, os.path.basename(csv_filename))
                    logger.info(f"Added {csv_filename} to zip archive {zip_filename}")

        # Remove the CSV files after adding them to the zip file
        for table_name in table_names:
            csv_filename = f"tmp/{table_name}.csv"
            if os.path.exists(csv_filename):
                os.remove(csv_filename)
                logger.info(f"Removed temporary file {csv_filename}")

    def export_table(self, table_name):
        """Export a given table to a csv file in the tmp directory"""
        resourcename = f"{table_name}Resource"
        try:
            resourceclass = getattr(registrar.admin, resourcename)
            dataset = resourceclass().export()
            filename = f"tmp/{table_name}.csv"
            with open(filename, "w") as outputfile:
                outputfile.write(dataset.csv)
            logger.info(f"Successfully exported {table_name} to {filename}")
        except AttributeError:
            logger.error(f"Resource class {resourcename} not found in registrar.admin")
        except Exception as e:
            logger.error(f"Failed to export {table_name}: {e}")
