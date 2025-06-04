"""Utilities for sending emails."""

import boto3
import logging
import textwrap
import re
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


def _normalize_and_flatten_email_list(email_or_emails):
    """
    Normalizes a single email string + flattens nested structures
    """

    # If passing in single email, it's wrapped into a list
    if isinstance(email_or_emails, str):
        return [email_or_emails]

    email_list = []

    for item in email_or_emails:
        # If it comes in as a list, "flatten" it recursively
        if isinstance(item, list):
            email_list.extend(_normalize_and_flatten_email_list(item))
        # Else if not a list, just add it to the list
        else:
            email_list.append(item)

    return email_list


def send_templated_email(  # noqa
    template_name: str,
    subject_template_name: str,
    to_addresses: list[str] = [],
    bcc_address: str = "",
    context={},
    attachment_file=None,
    wrap_email=False,
    cc_addresses: list[str] = [],
):
    """Send an email built from a template.

    to_addresses is a list and can contain many addresses.

    bcc_address currently only support single address.

    cc_addresses is a list and can contain many addresses. Emails not in the
    whitelist (if applicable) will be filtered out before sending.

    template_name and subject_template_name are relative to the same template
    context as Django's HTML templates. context gives additional information
    that the template may use.

    Raises EmailSendingError if:
        SES client could not be accessed
        No valid recipient addresses are provided
    """

    if context is None:
        context = {}

    to_addresses = _normalize_and_flatten_email_list(to_addresses)

    env_base_url = settings.BASE_URL
    # The regular expression is to get both http (localhost) and https (everything else)
    env_name = re.sub(r"^https?://", "", env_base_url).split(".")[0]
    # If NOT in prod, add env to the subject line
    # IE adds [GETGOV-RH] if we are in the -RH sandbox
    prefix = f"[{env_name.upper()}] " if not settings.IS_PRODUCTION else ""
    # If NOT in prod, update instances of "manage.get.gov" links to point to
    # current environment, ie "getgov-rh.app.cloud.gov"
    manage_url = env_base_url if not settings.IS_PRODUCTION else "https://manage.get.gov"

    context["manage_url"] = manage_url

    # by default assume we can send to all addresses (prod has no allowlist)
    sendable_cc_addresses = cc_addresses
    sendable_to_addresses = to_addresses

    if not settings.IS_PRODUCTION:  # type: ignore
        # Split into a function: C901 'send_templated_email' is too complex.
        # Raises an error if we cannot send an email (due to restrictions).
        # Does nothing otherwise.
        _can_send_email(sendable_to_addresses, bcc_address)

        # if we're not in prod, we need to check the allowlist for CC'ed addresses
        sendable_cc_addresses, blocked_cc_addresses = get_sendable_addresses(cc_addresses)
        sendable_to_addresses, blocked_to_addresses = get_sendable_addresses(to_addresses)

        if blocked_cc_addresses:
            logger.warning("Some CC'ed addresses were removed: %s.", blocked_cc_addresses)
        if blocked_to_addresses:
            logger.warning("Some CC'ed addresses were removed: %s.", blocked_to_addresses)

    template = get_template(template_name)
    email_body = template.render(context=context)

    # Do cleanup on the email body. For emails with custom content.
    if email_body:
        email_body.strip().lstrip("\n")

    # Update the subject to have prefix here versus every email
    subject_template = get_template(subject_template_name)
    subject = subject_template.render(context=context)
    subject = f"{prefix}{subject}"

    try:
        ses_client = boto3.client(
            "sesv2",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=settings.BOTO_CONFIG,
        )
        logger.info(f"Connected to SES client! Template name: {template_name} to {sendable_to_addresses}")
    except Exception as exc:
        logger.debug("E-mail unable to send! Could not access the SES client.")
        raise EmailSendingError("Could not access the SES client.") from exc

    destination = {}
    if to_addresses:
        destination["ToAddresses"] = sendable_to_addresses
    if bcc_address:
        destination["BccAddresses"] = [bcc_address]
    if cc_addresses:
        destination["CcAddresses"] = sendable_cc_addresses

    # make sure we don't try and send an email to nowhere
    if not destination:
        message = "Email unable to send, no valid recipients provided."
        raise EmailSendingError(message)

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
            logger.info(
                "Email sent to [%s], bcc [%s], cc %s", sendable_to_addresses, bcc_address, sendable_cc_addresses
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
                settings.DEFAULT_FROM_EMAIL, sendable_to_addresses, subject, email_body, attachment_file, ses_client
            )
            logger.info(
                "Email with attachment sent to [%s], bcc [%s], cc %s",
                sendable_to_addresses,
                bcc_address,
                sendable_cc_addresses,
            )

    except Exception as exc:
        raise EmailSendingError("Could not send SES email.") from exc


def _can_send_email(to_addresses, bcc_address):
    """Raises an EmailSendingError if we cannot send an email. Does nothing otherwise."""

    # testing below a global waffle flag which will not be associated with a user
    # or with http request, so pass None to flag_is_active
    if flag_is_active(None, "disable_email_sending"):  # type: ignore
        message = "Could not send email. Email sending is disabled due to flag 'disable_email_sending'."
        raise EmailSendingError(message)
    else:
        # Raise an email sending error if these doesn't exist within our whitelist.
        # If these emails don't exist, this function can handle that elsewhere.
        AllowedEmail = apps.get_model("registrar", "AllowedEmail")
        message = "Could not send email. The email '{}' does not exist within the whitelist."
        if to_addresses and not AllowedEmail.is_allowed_email(to_addresses):
            raise EmailSendingError(message.format(to_addresses))

        if bcc_address and not AllowedEmail.is_allowed_email(bcc_address):
            raise EmailSendingError(message.format(bcc_address))


def get_sendable_addresses(addresses: list[str]) -> tuple[list[str], list[str]]:
    """Checks whether a list of addresses can be sent to.

    Returns: a lists of all provided addresses that are ok to send to and a list of addresses that were blocked.

    Paramaters:

    addresses: a list of strings representing all addresses to be checked.
    """

    if flag_is_active(None, "disable_email_sending"):  # type: ignore
        message = "Could not send email. Email sending is disabled due to flag 'disable_email_sending'."
        logger.warning(message)
        return ([], [])
    else:
        AllowedEmail = apps.get_model("registrar", "AllowedEmail")
        allowed_emails = []
        blocked_emails = []
        for address in addresses:
            if AllowedEmail.is_allowed_email(address):
                allowed_emails.append(address)
            else:
                blocked_emails.append(address)

        return allowed_emails, blocked_emails


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
    msg["To"] = ", ".join(recipient)

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

    response = ses_client.send_raw_email(Source=sender, Destinations=recipient, RawMessage={"Data": msg.as_string()})

    return response
