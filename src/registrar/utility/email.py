"""Utilities for sending emails."""

import boto3

from django.conf import settings
from django.template.loader import get_template


def send_templated_email(template_name: str, to_address: str, context={}):
    """Send an email built from a template to one email address.

    template_name is relative to the same template context as Django's HTML
    templates. context gives additional information that the template may use.
    """

    template = get_template(template_name)
    email_body = template.render(context=context)

    ses_client = boto3.client(
        "sesv2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    ses_client.send_email(
        FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
        Destination={"ToAddresses": [to_address]},
        Content={
            "Subject": {"Data": "Thank you for applying for a .gov domain"},
            "Body": {"Text": {"Data": email_body}},
        },
    )
