"""Utilities for sending emails."""

import boto3
import logging
from django.conf import settings
from django.template.loader import get_template


logger = logging.getLogger(__name__)


class EmailSendingError(RuntimeError):
    """Local error for handling all failures when sending email."""

    pass


def send_templated_email(template_name: str, subject_template_name: str, to_address: str, bcc_address="", context={}):
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
        ses_client.send_email(
            FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            Destination=destination,
            Content={
                "Simple": {
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": email_body}},
                },
            },
        )
    except Exception as exc:
        raise EmailSendingError("Could not send SES email.") from exc
