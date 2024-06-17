"""Generates current-metadata.csv then uploads to S3 + sends email"""

import logging
import os
import pyzipper

from datetime import datetime

from django.core.management import BaseCommand
from django.conf import settings
from registrar.utility import csv_export
from io import StringIO
from ...utility.email import send_templated_email


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Emails a encrypted zip file containing a csv of our domains and domain requests"""
    help = (
        "Generates and uploads a domain-metadata.csv file to our S3 bucket "
        "which is based off of all existing Domains."
    )
    current_date = datetime.now().strftime("%m%d%Y")
    email_to: str

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument(
            "--emailTo",
            default=settings.DEFAULT_FROM_EMAIL,
            help="Defines where we should email this report",
        )

    def handle(self, **options):
        """Grabs the directory then creates domain-metadata.csv in that directory"""
        self.email_to = options.get("emailTo")

        # Don't email to DEFAULT_FROM_EMAIL when not prod.
        if not settings.IS_PRODUCTION and self.email_to == settings.DEFAULT_FROM_EMAIL:
            raise ValueError(
                "The --emailTo arg must be specified in non-prod environments, "
                "and the arg must not equal the DEFAULT_FROM_EMAIL value (aka: help@get.gov)."
            )

        logger.info("Generating report...")
        zip_filename = f"domain-metadata-{self.current_date}.zip"
        try:
            self.email_current_metadata_report(zip_filename)
        except Exception as err:
            # TODO - #1317: Notify operations when auto report generation fails
            raise err
        else:
            logger.info(f"Success! Created {zip_filename} and successfully sent out an email!")

    def email_current_metadata_report(self, zip_filename):
        """Creates a current-metadata.csv file under the specified directory,
        then uploads it to a AWS S3 bucket. This is done for resiliency
        reasons in the event our application goes down and/or the email
        cannot send -- we'll still be able to grab info from the S3
        instance"""
        reports = {
            "Domain report": {
                "report_filename": f"domain-metadata-{self.current_date}.csv",
                "report_function": csv_export.export_data_type_to_csv,
            },
            "Domain request report": {
                "report_filename": f"domain-request-metadata-{self.current_date}.csv",
                "report_function": csv_export.DomainRequestExport.export_full_domain_request_report,
            },
        }
        # Set the password equal to our content in SECRET_ENCRYPT_METADATA.
        # For local development, this will be "devpwd" unless otherwise set.
        override = settings.SECRET_ENCRYPT_METADATA is None and not settings.IS_PRODUCTION
        password = "devpwd" if override else settings.SECRET_ENCRYPT_METADATA

        encrypted_zip_in_bytes = self.get_encrypted_zip(zip_filename, reports, password)

        # Send the metadata file that is zipped
        send_templated_email(
            template_name="emails/metadata_body.txt",
            subject_template_name="emails/metadata_subject.txt",
            to_address=self.email_to,
            context={"current_date_str": datetime.now().strftime("%Y-%m-%d")},
            attachment_file=encrypted_zip_in_bytes,
        )


    def get_encrypted_zip(self, zip_filename, reports, password):
        """Helper function for encrypting the attachment file"""

        # Using ZIP_DEFLATED bc it's a more common compression method supported by most zip utilities and faster
        # We could also use compression=pyzipper.ZIP_LZMA if we are looking for smaller file size
        with pyzipper.AESZipFile(
            zip_filename, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as f_out:
            f_out.setpassword(str.encode(password))
            for report_name, report_value in reports.items():
                report_filename = report_value["report_filename"]
                report_function = report_value["report_function"]

                report = self.write_and_return_report(report_function)
                f_out.writestr(report_filename, report)
                logger.info(f"Generated {report_name}")

        # Get the final report for emailing purposes
        with open(zip_filename, "rb") as file_data:
            attachment_in_bytes = file_data.read()

        return attachment_in_bytes

    def write_and_return_report(self, report_function):
        """Writes a report to a StringIO object given a report_function and returns the string."""
        report_bytes = StringIO()
        report_function(report_bytes)

        # Rewind the buffer to the beginning after writing
        report_bytes.seek(0)
        return report_bytes.read()
