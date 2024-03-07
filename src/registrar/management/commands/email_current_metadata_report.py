"""Generates current-metadata.csv then uploads to S3 + sends email"""

import logging
import os
import pyzipper

from datetime import datetime

from django.core.management import BaseCommand
from django.conf import settings
from registrar.utility import csv_export
from registrar.utility.s3_bucket import S3ClientHelper
from ...utility.email import send_templated_email


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Generates and uploads a domain-metadata.csv file to our S3 bucket "
        "which is based off of all existing Domains."
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
        """Grabs the directory then creates domain-metadata.csv in that directory"""
        file_name = "domain-metadata.csv"
        # Ensures a slash is added
        directory = os.path.join(options.get("directory"), "")
        check_path = options.get("checkpath")

        logger.info("Generating report...")
        try:
            self.email_current_metadata_report(directory, file_name, check_path)
        except Exception as err:
            # TODO - #1317: Notify operations when auto report generation fails
            raise err
        else:
            logger.info(f"Success! Created {file_name} and successfully sent out an email!")

    def email_current_metadata_report(self, directory, file_name, check_path):
        """Creates a current-metadata.csv file under the specified directory,
        then uploads it to a AWS S3 bucket. This is done for resiliency
        reasons in the event our application goes down and/or the email
        cannot send -- we'll still be able to grab info from the S3
        instance"""
        s3_client = S3ClientHelper()
        file_path = os.path.join(directory, file_name)

        # Generate a file locally for upload
        with open(file_path, "w") as file:
            csv_export.export_data_type_to_csv(file)

        if check_path and not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find newly created file at '{file_path}'")

        s3_client.upload_file(file_path, file_name)

        # Set zip file name
        current_date = datetime.now().strftime("%m%d%Y")
        current_filename = f"domain-metadata-{current_date}.zip"

        # Pre-set zip file name
        encrypted_metadata_output = current_filename

        # Set context for the subject
        current_date_str = datetime.now().strftime("%Y-%m-%d")

        # TODO: Update secret in getgov-credentials via cloud.gov and my own .env when merging

        # Encrypt the metadata
        encrypted_metadata_in_bytes = self._encrypt_metadata(
            s3_client.get_file(file_name), encrypted_metadata_output, str.encode(settings.SECRET_ENCRYPT_METADATA)
        )

        # Send the metadata file that is zipped
        send_templated_email(
            template_name="emails/metadata_body.txt",
            subject_template_name="emails/metadata_subject.txt",
            # to_address=settings.DEFAULT_FROM_EMAIL, # TODO: Uncomment this when ready to merge
            to_address="rebecca.hsieh@truss.works <rebecca.hsieh@truss.works>",
            context={"current_date_str": current_date_str},
            attachment_file=encrypted_metadata_in_bytes,
        )

    def _encrypt_metadata(self, input_file, output_file, password):
        """Helper function for encrypting the attachment file"""
        current_date = datetime.now().strftime("%m%d%Y")
        current_filename = f"domain-metadata-{current_date}.csv"
        # Using ZIP_DEFLATED bc it's a more common compression method supported by most zip utilities and faster
        # We could also use compression=pyzipper.ZIP_LZMA if we are looking for smaller file size
        with pyzipper.AESZipFile(
            output_file, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as f_out:
            f_out.setpassword(password)
            f_out.writestr(current_filename, input_file)
        with open(output_file, "rb") as file_data:
            attachment_in_bytes = file_data.read()
        return attachment_in_bytes
