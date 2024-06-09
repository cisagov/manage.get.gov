import logging
import argparse
import sys

from django.core.management import BaseCommand

from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)
from registrar.models.contact import Contact
from registrar.models.user import User
from registrar.models.utility.domain_helper import DomainHelper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Copy first and last names from a contact to
    a related user if it exists and if its first and last name
    properties are null or blank strings."""

    # ======================================================
    # ===================== ARGUMENTS  =====================
    # ======================================================
    def add_arguments(self, parser):
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

    # ======================================================
    # ===================== PRINTING  ======================
    # ======================================================
    def print_debug_mode_statements(self, debug_on: bool):
        """Prints additional terminal statements to indicate if --debug
        or --limitParse are in use"""
        TerminalHelper.print_conditional(
            debug_on,
            f"""{TerminalColors.OKCYAN}
            ----------DEBUG MODE ON----------
            Detailed print statements activated.
            {TerminalColors.ENDC}
            """,
        )

    def print_summary_of_findings(
        self,
        skipped_contacts,
        eligible_users,
        processed_users,
        debug_on,
    ):
        """Prints to terminal a summary of findings from
        copying first and last names from contacts to users"""

        total_eligible_users = len(eligible_users)
        total_skipped_contacts = len(skipped_contacts)
        total_processed_users = len(processed_users)

        logger.info(
            f"""{TerminalColors.OKGREEN}
            ============= FINISHED ===============
            Skipped {total_skipped_contacts} contacts
            Found {total_eligible_users} users linked to contacts
            Processed {total_processed_users} users
            {TerminalColors.ENDC}
            """  # noqa
        )

        # DEBUG:
        TerminalHelper.print_conditional(
            debug_on,
            f"""{TerminalColors.YELLOW}
            ======= DEBUG OUTPUT =======
            Users who have a linked contact:
            {eligible_users}

            Processed users (users who have a linked contact and a missing first or last name):
            {processed_users}

            ===== SKIPPED CONTACTS =====
            {skipped_contacts}

            {TerminalColors.ENDC}
            """,
        )

    # ======================================================
    # ===================    USER    =====================
    # ======================================================
    def update_user(self, contact: Contact, debug_on: bool):
        """Given a contact with a first_name and last_name, find & update an existing
        corresponding user if her first_name and last_name are null.

        Returns tuple of eligible (is linked to the contact) and processed
        (first and last are blank) users.
        """

        user_exists = User.objects.filter(contact=contact).exists()
        if user_exists:
            try:
                # ----------------------- UPDATE USER -----------------------
                # ---- GET THE USER
                eligible_user = User.objects.get(contact=contact)
                processed_user = None
                # DEBUG:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"""{TerminalColors.YELLOW}
                    > Found linked user for contact:
                    {contact} {contact.email} {contact.first_name} {contact.last_name}
                    > The linked user is {eligible_user} {eligible_user.username}
                    {TerminalColors.ENDC}""",  # noqa
                )

                # Get the fields that exist on both User and Contact. Excludes id.
                common_fields = DomainHelper.get_common_fields(User, Contact)
                if "email" in common_fields:
                    # Don't change the email field.
                    common_fields.remove("email")

                for field in common_fields:
                    # Grab the value that contact has stored for this field
                    new_value = getattr(contact, field)

                    # Set it on the user field
                    setattr(eligible_user, field, new_value)

                eligible_user.save()
                processed_user = eligible_user

                return (
                    eligible_user,
                    processed_user,
                )

            except Exception as error:
                logger.warning(
                    f"""
                    {TerminalColors.FAIL}
                    !!! ERROR: An exception occured in the
                    User table for the following user:
                    {contact.email} {contact.first_name} {contact.last_name}

                    Exception is: {error}
                    ----------TERMINATING----------"""
                )
                sys.exit()
        else:
            return None, None

    # ======================================================
    # ================= PROCESS CONTACTS  ==================
    # ======================================================

    def process_contacts(
        self,
        debug_on,
        skipped_contacts=[],
        eligible_users=[],
        processed_users=[],
    ):
        for contact in Contact.objects.all():
            TerminalHelper.print_conditional(
                debug_on,
                f"{TerminalColors.OKCYAN}"
                "Processing Contact: "
                f"{contact.email},"
                f" {contact.first_name},"
                f" {contact.last_name}"
                f"{TerminalColors.ENDC}",
            )

            # ======================================================
            # ====================== USER  =======================
            (eligible_user, processed_user) = self.update_user(contact, debug_on)

            debug_string = ""
            if eligible_user:
                # ---------------- UPDATED ----------------
                eligible_users.append(contact.email)
                debug_string = f"eligible user: {eligible_user}"
                if processed_user:
                    processed_users.append(contact.email)
                    debug_string = f"processed user: {processed_user}"
            else:
                skipped_contacts.append(contact.email)
                debug_string = f"skipped user: {contact.email}"

            # DEBUG:
            TerminalHelper.print_conditional(
                debug_on,
                (f"{TerminalColors.OKCYAN} {debug_string} {TerminalColors.ENDC}"),
            )

        return (
            skipped_contacts,
            eligible_users,
            processed_users,
        )

    # ======================================================
    # ===================== HANDLE  ========================
    # ======================================================
    def handle(
        self,
        **options,
    ):
        """Parse entries in Contact table
        and update valid corresponding entries in the
        User table."""

        # grab command line arguments and store locally...
        debug_on = options.get("debug")

        self.print_debug_mode_statements(debug_on)

        logger.info(
            f"""{TerminalColors.OKCYAN}
            ==========================
            Beginning Data Transfer
            ==========================
            {TerminalColors.ENDC}"""
        )

        logger.info(
            f"""{TerminalColors.OKCYAN}
            ========= Adding Domains and Domain Invitations =========
            {TerminalColors.ENDC}"""
        )
        (
            skipped_contacts,
            eligible_users,
            processed_users,
        ) = self.process_contacts(
            debug_on,
        )

        self.print_summary_of_findings(
            skipped_contacts,
            eligible_users,
            processed_users,
            debug_on,
        )
