"""Data migration: Send domain invitations once to existing customers."""

import logging
import copy
import time

from django.core.management import BaseCommand
from registrar.models import TransitionDomain
from ...utility.email import send_templated_email, EmailSendingError
from typing import List

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send domain invitations once to existing customers."

    # this array is used to store and process the transition_domains
    transition_domains: List[str] = []
    # this array is used to store domains with errors, which are not
    # sent emails; this array is used to update the succesful
    # transition_domains to email_sent=True, and also to report
    # out errors
    domains_with_errors: List[str] = []
    # this array is used to store email_context; each item in the array
    # contains the context for a single email; single emails may be 1
    # or more transition_domains, as they are grouped by username
    emails_to_send: List[str] = []

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "-s",
            "--send_emails",
            action="store_true",
            default=False,
            dest="send_emails",
            help="Send emails ",
        )

        parser.add_argument("emails", nargs="*", help="Email addresses to send invitations to")

    def handle(self, **options):
        """Process the objects in TransitionDomain."""

        logger.info("checking domains and preparing emails")

        if options["emails"]:
            # this option is a list of email addresses
            self.transition_domains = TransitionDomain.objects.filter(
                username__in=options["emails"],
                email_sent=False,
            ).order_by("username")
        else:
            # Get all TransitionDomain objects
            self.transition_domains = TransitionDomain.objects.filter(
                email_sent=False,
            ).order_by("username")
        logger.info("Found %d transition domains", len(self.transition_domains))

        self.build_emails_to_send_array()
        logger.info("Prepared %d emails to send", len(self.emails_to_send))

        if options["send_emails"]:
            logger.info("about to send emails")
            self.send_emails()
            logger.info("done sending emails")

            logger.info("done sending emails and updating transition_domains")
        else:
            logger.info("not sending emails")
            for email_context in self.emails_to_send:
                logger.info(
                    "would send email to %s for %s",
                    email_context["email"],
                    email_context["domains"],
                )

    def build_emails_to_send_array(self):
        """this method sends emails to distinct usernames"""

        # data structure to hold email context for a single email;
        # transition_domains ordered by username, a single email_context
        # may include information from more than one transition_domain
        email_context = {"email": ""}

        # loop through all transition_domains; group them by username
        # into emails_to_send_array
        for transition_domain in self.transition_domains:
            # attempt to get the domain from domain objects; if there is
            # an error getting the domain, skip this domain and add it to
            # domains_with_errors
            try:
                # if prior username does not match current username
                if not email_context["email"] or email_context["email"] != transition_domain.username:
                    # if not first in list of transition_domains
                    if email_context["email"]:
                        # append the email context to the emails_to_send array
                        self.emails_to_send.append(copy.deepcopy(email_context))
                    email_context["domains"] = []
                email_context["email"] = transition_domain.username
                email_context["domains"].append(transition_domain.domain_name)
            except Exception as err:
                # error condition if domain not in database
                self.domains_with_errors.append(copy.deepcopy(transition_domain.domain_name))
                logger.error(f"error retrieving domain {transition_domain.domain_name}: {err}")
        # if there are at least one more transition domains than errors,
        # then append one more item
        if len(self.transition_domains) > len(self.domains_with_errors):
            self.emails_to_send.append(email_context)

    def send_emails(self):
        if len(self.emails_to_send) > 0:
            for email_data in self.emails_to_send:
                self.send_email(email_data)
                # wait 1/10 second until sending the next email to keep us
                # safely under a rate of 10 emails per second
                time.sleep(0.1)
        else:
            logger.info("no emails to send")

    def send_email(self, email_data):
        try:
            send_templated_email(
                "emails/transition_domain_invitation.txt",
                "emails/transition_domain_invitation_subject.txt",
                to_address=email_data["email"],
                context={
                    "domains": email_data["domains"],
                },
            )
            # success message is logged
            logger.info(
                f"email sent successfully to {email_data['email']} for "
                f"{[domain for domain in email_data['domains']]}"
            )
        except EmailSendingError as err:
            logger.error(
                f"email did not send successfully to {email_data['email']} "
                f"for {[domain for domain in email_data['domains']]}"
                f": {err}"
            )
            # if email failed to send, set error in domains_with_errors for each
            # domain in the email so that transition domain email_sent is not set
            # to True
            for domain in email_data["domains"]:
                self.domains_with_errors.append(domain)
        else:
            # email was sent no exception, mark all these transition domains
            # as email_sent.
            this_email = email_data["email"]
            for domain_name in email_data["domains"]:
                # self.transition_domains is a queryset so we can sub-select
                # from it and use the objects to mark them as sent
                this_transition_domain = self.transition_domains.get(username=this_email, domain_name=domain_name)
                this_transition_domain.email_sent = True
                this_transition_domain.save()
