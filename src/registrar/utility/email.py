"""Utilities for sending emails."""

import boto3
import logging
from django.conf import settings
from django.template.loader import get_template


logger = logging.getLogger(__name__)


class EmailSendingError(RuntimeError):
    """Local error for handling all failures when sending email."""

    pass


def send_templated_email(template_name: str, subject_template_name: str, to_address: str, context={}):
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

    # Are we okay with passing in "attachment" var in as boolean parameter
    # If so, TODO: add attachment boolean to other functions
    try:
        #if not attachment: 
        ses_client.send_email(
            FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            Destination={"ToAddresses": [to_address]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": email_body}},
                },
            },
        )
        # else: # has attachment
            # same as above but figure out how to attach a file
            # via boto3 "boto3 SES file attachment"
            # we also want this to only send to the help email
        
            # from email.mime.multipart import MIMEMultipart
            # from email.mime.text import MIMEText
            # from email.mime.application import MIMEApplication

            # sender_email = 'sender@example.com'
            # recipient_email = 'help@get.gov'
            # subject = 'DOTGOV-Full Domain Metadata'
            # body = 'Domain metadata email, should have an attachment included change here later.'
            # attachment_path = 'path/to/attachment/file.pdf'
            # aws_region = 'sesv2'

            # response = send_email_with_attachment(sender_email, recipient_email, subject, body, attachment_path, aws_region)
            # print(response)
    except Exception as exc:
        raise EmailSendingError("Could not send SES email.") from exc


# def send_email_with_attachment(sender, recipient, subject, body, attachment_path, aws_region):
            #     # Create a multipart/mixed parent container
            #     msg = MIMEMultipart('mixed')
            #     msg['Subject'] = subject
            #     msg['From'] = sender_email
            #     msg['To'] = recipient_email

            #     # Add the text part
            #     text_part = MIMEText(body, 'plain')
            #     msg.attach(text_part)

            #     # Add the attachment part
            #     with open(attachment_path, 'rb') as attachment_file:
            #         attachment_data = attachment_file.read()
            #     attachment_part = MIMEApplication(attachment_data)
            #     attachment_part.add_header('Content-Disposition', f'attachment; filename="{attachment_path}"')
            #     msg.attach(attachment_part)

            #     # Send the email
            #     response = ses_client.send_raw_email(
            #         Source=sender,
            #         Destinations=[recipient],
            #         RawMessage={'Data': msg.as_string()}
            #     )

            #     ses_client.send_email(
            #     FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
            #     Destination={"ToAddresses": [to_address]},
            #     Content={
            #         "Simple": {
            #             "Subject": {"Data": subject},
            #             "Body": {"Text": {"Data": email_body}},
            #         },
            #     },
            # )