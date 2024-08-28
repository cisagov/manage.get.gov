"""Utilities for sending emails."""

import boto3
import logging
import textwrap
from datetime import datetime
from django.apps import apps
from django.conf import settings
from django.template.loader import get_template
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from waffle import flag_is_active


logger = logging.getLogger(__name__)


class EmailSendingError(RuntimeError):
    """Local error for handling all failures when sending email."""

    pass


def send_templated_email(
    template_name: str,
    subject_template_name: str,
    to_address: str,
    bcc_address="",
    context={},
    attachment_file=None,
    wrap_email=False,
):
    """Send an email built from a template to one email address.

    template_name and subject_template_name are relative to the same template
    context as Django's HTML templates. context gives additional information
    that the template may use.

    Raises EmailSendingError if SES client could not be accessed
    """

    if not settings.IS_PRODUCTION:  # type: ignore
        # Split into a function: C901 'send_templated_email' is too complex.
        # Raises an error if we cannot send an email (due to restrictions).
        # Does nothing otherwise.
        _can_send_email(to_address, bcc_address)

    template = get_template(template_name)
    email_body = template.render(context=context)

    # Do cleanup on the email body. For emails with custom content.
    if email_body:
        email_body.strip().lstrip("\n")

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
        logger.info(f"An email was sent! Template name: {template_name} to {to_address}")
    except Exception as exc:
        logger.debug("E-mail unable to send! Could not access the SES client.")
        raise EmailSendingError("Could not access the SES client.") from exc

    destination = {"ToAddresses": [to_address]}
    if bcc_address:
        destination["BccAddresses"] = [bcc_address]

    try:
        if not attachment_file:
            # Wrap the email body to a maximum width of 80 characters per line.
            # Not all email clients support CSS to do this, and our .txt files require parsing.
            if wrap_email:
                email_body = wrap_text_and_preserve_paragraphs(email_body, width=80)

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
        else:
            ses_client = boto3.client(
                "ses",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=settings.BOTO_CONFIG,
            )
            send_email_with_attachment(
                settings.DEFAULT_FROM_EMAIL, to_address, subject, email_body, attachment_file, ses_client
            )
    except Exception as exc:
        raise EmailSendingError("Could not send SES email.") from exc


def _can_send_email(to_address, bcc_address):
    """Raises an EmailSendingError if we cannot send an email. Does nothing otherwise."""

    if flag_is_active(None, "disable_email_sending"):  # type: ignore
        message = "Could not send email. Email sending is disabled due to flag 'disable_email_sending'."
        raise EmailSendingError(message)
    else:
        # Raise an email sending error if these doesn't exist within our whitelist.
        # If these emails don't exist, this function can handle that elsewhere.
        AllowedEmail = apps.get_model("registrar", "AllowedEmail")
        message = "Could not send email. The email '{}' does not exist within the whitelist."
        if to_address and not AllowedEmail.is_allowed_email(to_address):
            raise EmailSendingError(message.format(to_address))

        if bcc_address and not AllowedEmail.is_allowed_email(bcc_address):
            raise EmailSendingError(message.format(bcc_address))


def wrap_text_and_preserve_paragraphs(text, width):
    """
    Wraps text to `width` preserving newlines; splits on '\n', wraps segments, rejoins with '\n'.
    Args:
        text (str): Text to wrap.
        width (int): Max width per line, default 80.

    Returns:
        str: Wrapped text with preserved paragraph structure.
    """
    # Split text into paragraphs by newlines
    paragraphs = text.split("\n")

    # Add \n to any line that exceeds our max length
    wrapped_paragraphs = [textwrap.fill(paragraph, width=width) for paragraph in paragraphs]

    # Join paragraphs with double newlines
    return "\n".join(wrapped_paragraphs)


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
