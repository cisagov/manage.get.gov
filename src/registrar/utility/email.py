"""Utilities for sending emails."""

import boto3
import logging
from datetime import datetime
from django.conf import settings
from django.template.loader import get_template
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


logger = logging.getLogger(__name__)


class EmailSendingError(RuntimeError):
    """Local error for handling all failures when sending email."""

    pass


def send_templated_email(template_name: str, subject_template_name: str, to_address: str, bcc_address="", context={}, file: str = None):
    """Send an email built from a template to one email address.

    template_name and subject_template_name are relative to the same template
    context as Django's HTML templates. context gives additional information
    that the template may use.
    """
    logger.info(f"An email was sent! Template name: {template_name} to {to_address}")
    template = get_template(template_name)
    email_body = template.render(context=context)

    subject_template = get_template(subject_template_name)
    subject = subject_template.render(context=context)

    try:
        ses_client = boto3.client(
            "sesv2",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=settings.BOTO_CONFIG,
        )
    except Exception as exc:
        raise EmailSendingError("Could not access the SES client.") from exc

    destination = {"ToAddresses": [to_address]}
    if bcc_address:
        destination["BccAddresses"] = [bcc_address]

    try:

        if file is None:
            ses_client.send_email(
                FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
                Destination={"ToAddresses": [to_address]},
                Content={
                    "Simple": {
                        "Subject": {"Data": subject},
                        "Body": {"Text": {"Data": email_body}},
                    },
                }
            )
        else:
            ses_client = boto3.client(
                "ses",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=settings.BOTO_CONFIG,
            )
            response = send_email_with_attachment(
                settings.DEFAULT_FROM_EMAIL, to_address, subject, email_body, file, ses_client
            )
            # TODO: Remove this print statement when ready to merge,
            # leaving rn for getting error codes in case
            print("Response from send_email_with_attachment_is:", response)
    except Exception as exc:
        raise EmailSendingError("Could not send SES email.") from exc


def send_email_with_attachment(sender, recipient, subject, body, attachment_file, ses_client):
    # Create a multipart/mixed parent container
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    # Add the text part
    text_part = MIMEText(body, "plain")
    msg.attach(text_part)

    # Add the attachment part
    attachment_part = MIMEApplication(attachment_file)
    # Adding attachment header + filename that the attachment will be called
    current_date = datetime.now().strftime("%m%d%Y")
    current_filename = f"domain-metadata-{current_date}.zip"
    attachment_part.add_header("Content-Disposition", f'attachment; filename="{current_filename}"')
    msg.attach(attachment_part)

    response = ses_client.send_raw_email(Source=sender, Destinations=[recipient], RawMessage={"Data": msg.as_string()})
    return response
