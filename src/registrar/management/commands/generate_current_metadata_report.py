"""Generates current-metadata.csv then uploads to S3 + sends email"""

import logging
import os
import pyzipper

from django.core.management import BaseCommand
from django.conf import settings
from registrar.utility import csv_export
from registrar.utility.s3_bucket import S3ClientHelper
from ...utility.email import send_templated_email, EmailSendingError


logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = (
        "Generates and uploads a current-metadata.csv file to our S3 bucket " "which is based off of all existing Domains."
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
        """Grabs the directory then creates current-metadata.csv in that directory"""
        file_name = "current-metadata.csv"
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        check_path = options.get("checkpath")

        logger.info("Generating report...")
        try:
            self.generate_current_metadata_report(directory, file_name, check_path)
        except Exception as err:
            # TODO - #1317: Notify operations when auto report generation fails
            raise err
        else:
            logger.info(f"Success! Created {file_name}")

    def generate_current_metadata_report(self, directory, file_name, check_path):
        """Creates a current-full.csv file under the specified directory,
        then uploads it to a AWS S3 bucket"""
        s3_client = S3ClientHelper()
        file_path = os.path.join(directory, file_name)

        # Generate a file locally for upload
        with open(file_path, "w") as file:
            csv_export.export_data_type_to_csv(file)

        if check_path and not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find newly created file at '{file_path}'")

        # Upload this generated file for our S3 instance
        s3_client.upload_file(file_path, file_name)
        """
        We want to make sure to upload to s3 for back up
        And now we also want to get the file and encrypt it so we can send it in an email
        """

        # Encrypt metadata into a zip file

        # pre-setting zip file name 
        encrypted_metadata_output = 'encrypted_metadata.zip'

        # Secret is encrypted into getgov-credentials
        # TODO: Update secret in getgov-credentials via cloud.gov and my own .env when ready
        
        # Encrypt the metadata 
        # TODO: UPDATE SECRET_ENCRYPT_METADATA pw getgov-credentials on stable
        encrypted_metadata = self._encrypt_metadata(s3_client.get_file(file_name), encrypted_metadata_output, str.encode(settings.SECRET_ENCRYPT_METADATA))
        print("encrypted_metadata is:", encrypted_metadata)
        print("the type is: ", type(encrypted_metadata))
        # Send the metadata file that is zipped
        # TODO: Make new .txt files
        send_templated_email(
            "emails/metadata_body.txt",
            "emails/metadata_subject.txt",
            to_address="rebecca.hsieh@truss.works", # TODO: Update to settings.DEFAULT_FROM_EMAIL once tested
            file=encrypted_metadata,
        )

    def _encrypt_metadata(self, input_file, output_file, password):
        # Using ZIP_DEFLATED bc it's a more common compression method supported by most zip utilities and faster
        # We could also use compression=pyzipper.ZIP_LZMA if we are looking for smaller file size
        with pyzipper.AESZipFile(output_file, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as f_out:
            f_out.setpassword(password)
            f_out.writestr('encrypted_metadata.txt', input_file)
        return output_file

