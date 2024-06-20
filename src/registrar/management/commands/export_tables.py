from django.core.paginator import Paginator
import logging
import os
import pyzipper
import tablib
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

                # Define the tmp directory and the file pattern
                tmp_dir = "tmp"
                pattern = f"{table_name}_"
                zip_file_path = os.path.join(tmp_dir, "exported_files.zip")

                # Find all files that match the pattern
                matching_files = [file for file in os.listdir(tmp_dir) if file.startswith(pattern)]
                for file_path in matching_files:
                    # Add each file to the zip archive
                    zipf.write(f"tmp/{file_path}", os.path.basename(file_path))
                    logger.info(f"Added {file_path} to {zip_file_path}")

                    # Remove the file after adding to zip
                    os.remove(f"tmp/{file_path}")
                    logger.info(f"Removed {file_path}")

    def export_table(self, table_name):
        """Export a given table to csv files in the tmp directory"""
        resourcename = f"{table_name}Resource"
        try:
            resourceclass = getattr(registrar.admin, resourcename)
            dataset = resourceclass().export()
            if not isinstance(dataset, tablib.Dataset):
                raise ValueError(f"Exported data from {resourcename} is not a tablib.Dataset")

            # Determine the number of rows per file
            rows_per_file = 10000

            # Use Paginator to handle splitting the dataset
            paginator = Paginator(dataset.dict, rows_per_file)
            num_files = paginator.num_pages

            logger.info(f"splitting {table_name} into {num_files} files")

            # Export each page to a separate file
            for page_num in paginator.page_range:
                page = paginator.page(page_num)

                # Create a new dataset for the chunk
                chunk = tablib.Dataset(headers=dataset.headers)
                for row_dict in page.object_list:
                    row = [row_dict[header] for header in dataset.headers]
                    chunk.append(row)

                # Export the chunk to a new file
                filename = f"tmp/{table_name}_{page_num}.csv"
                with open(filename, "w") as f:
                    f.write(chunk.export("csv"))

            logger.info(f"Successfully exported {table_name} into {num_files} files.")

        except AttributeError:
            logger.error(f"Resource class {resourcename} not found in registrar.admin")
        except Exception as e:
            logger.error(f"Failed to export {table_name}: {e}")
