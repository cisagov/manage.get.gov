"""Generates current-metadata.csv then uploads to S3 + sends email"""

import logging
import pyzipper

from datetime import datetime

from django.core.management import BaseCommand
from django.conf import settings
from registrar.utility import csv_export
from io import StringIO
from ...utility.email import send_templated_email, EmailSendingError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Emails a encrypted zip file containing a csv of our domains and domain requests"""

    help = (
        "Generates and uploads a domain-metadata.csv file to our S3 bucket "
        "which is based off of all existing Domains."
    )
    current_date = datetime.now().strftime("%m%d%Y")

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument(
            "--emailTo",
            default=settings.DEFAULT_FROM_EMAIL,
            help="Defines where we should email this report",
        )

    def handle(self, **options):
        """Grabs the directory then creates domain-metadata.csv in that directory"""
        zip_filename = f"domain-metadata-{self.current_date}.zip"
        email_to = options.get("emailTo")

        # Don't email to DEFAULT_FROM_EMAIL when not prod.
        if not settings.IS_PRODUCTION and email_to == settings.DEFAULT_FROM_EMAIL:
            raise ValueError(
                "The --emailTo arg must be specified in non-prod environments, "
                "and the arg must not equal the DEFAULT_FROM_EMAIL value (aka: help@get.gov)."
            )

        logger.info("Generating report...")
        try:
            success = self.email_current_metadata_report(zip_filename, email_to)
            if not success:
                # TODO - #1317: Notify operations when auto report generation fails
                raise EmailSendingError("Report was generated but failed to send via email.")
        except Exception as err:
            raise err
        else:
            logger.info(f"Success! Created {zip_filename} and successfully sent out an email!")

    def email_current_metadata_report(self, zip_filename, email_to):
        """Emails a password protected zip containing domain-metadata and domain-request-metadata"""
        reports = {
            "Domain report": {
                "report_filename": f"domain-metadata-{self.current_date}.csv",
                "report_function": csv_export.DomainDataType.export_data_to_csv,
            },
            "Domain request report": {
                "report_filename": f"domain-request-metadata-{self.current_date}.csv",
                "report_function": csv_export.DomainRequestDataFull.export_data_to_csv,
            },
        }

        # Set the password equal to our content in SECRET_ENCRYPT_METADATA.
        # For local development, this will be "devpwd" unless otherwise set.
        # Uncomment these lines (and comment out the line after) if you want to use this:
        # override = settings.SECRET_ENCRYPT_METADATA is None and not settings.IS_PRODUCTION
        # password = "devpwd" if override else settings.SECRET_ENCRYPT_METADATA
        password = settings.SECRET_ENCRYPT_METADATA
        if not password:
            raise ValueError("No password was specified for this zip file.")

        encrypted_zip_in_bytes = self.get_encrypted_zip(zip_filename, reports, password)

        # Send the metadata file that is zipped
        try:
            send_templated_email(
                template_name="emails/metadata_body.txt",
                subject_template_name="emails/metadata_subject.txt",
                to_addresses=email_to,
                context={"current_date_str": datetime.now().strftime("%Y-%m-%d")},
                attachment_file=encrypted_zip_in_bytes,
            )
            return True
        except EmailSendingError as err:
            logger.error(
                "Failed to send metadata email:\n"
                f"  Subject: metadata_subject.txt\n"
                f"  To: {email_to}\n"
                f"  Error: {err}",
                exc_info=True,
            )
            return False

    def get_encrypted_zip(self, zip_filename, reports, password):
        """Helper function for encrypting the attachment file"""

        # Using ZIP_DEFLATED bc it's a more common compression method supported by most zip utilities and faster
        # We could also use compression=pyzipper.ZIP_LZMA if we are looking for smaller file size
        with pyzipper.AESZipFile(
            zip_filename, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as f_out:
            f_out.setpassword(str.encode(password))
            for report_name, report in reports.items():
                logger.info(f"Generating {report_name}")
                report_content = self.write_and_return_report(report["report_function"])
                f_out.writestr(report["report_filename"], report_content)

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
