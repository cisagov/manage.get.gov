"""Utilities for sending emails."""

import boto3

from django.conf import settings
from django.template.loader import get_template


class EmailSendingError(RuntimeError):

    """Local error for handling all failures when sending email."""

    pass


def send_templated_email(template_name: str, to_address: str, context={}):
    """Send an email built from a template to one email address.

    template_name is relative to the same template context as Django's HTML
    templates. context gives additional information that the template may use.
    """

    template = get_template(template_name)
    email_body = template.render(context=context)

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

    try:
        ses_client.send_email(
            FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            Destination={"ToAddresses": [to_address]},
            Content={
                "Simple": {
                    "Subject": {"Data": "Thank you for applying for a .gov domain"},
                    "Body": {"Text": {"Data": email_body}},
                },
            },
        )
    except Exception as exc:
        raise EmailSendingError("Could not send SES email.") from exc
