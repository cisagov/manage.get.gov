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

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Copy first and last names from a contact to
    a related user if it exists and if its first and last name
    properties are null"""

    # ======================================================
    # ===================== ARGUMENTS  =====================
    # ======================================================
    def add_arguments(self, parser):
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse",
            default=0,
            help="Sets max number of records (contacts) to copy, set to 0 to copy all entries",
        )

    # ======================================================
    # ===================== PRINTING  ======================
    # ======================================================
    def print_debug_mode_statements(self, debug_on: bool, debug_max_entries_to_parse: int):
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
        TerminalHelper.print_conditional(
            debug_max_entries_to_parse > 0,
            f"""{TerminalColors.OKCYAN}
            ----------LIMITER ON----------
            Parsing of entries will be limited to
            {debug_max_entries_to_parse} lines per file.")
            Detailed print statements activated.
            {TerminalColors.ENDC}
            """,
        )

    def parse_limit_reached(self, debug_max_entries_to_parse: bool, total_rows_parsed: int) -> bool:
        if debug_max_entries_to_parse > 0 and total_rows_parsed/2 >= debug_max_entries_to_parse:
            logger.info(
                f"""{TerminalColors.YELLOW}
                ----PARSE LIMIT REACHED.  HALTING PARSER.----
                {TerminalColors.ENDC}
                """
            )
            return True
        return False

    def print_summary_of_findings(
        self,
        updated_user_records,
        skipped_contacts,
        debug_on,
    ):
        """Prints to terminal a summary of findings from
        copying first and last names from contacts to users"""

        total_updated_user_entries = len(updated_user_records)
        total_skipped_contacts_entries = len(skipped_contacts)

        logger.info(
            f"""{TerminalColors.OKGREEN}
            ============= FINISHED ===============
            Updated {total_updated_user_entries} users
            Skipped {total_skipped_contacts_entries} contacts
            {TerminalColors.ENDC}
            """  # noqa
        )
            
        # DEBUG:
        TerminalHelper.print_conditional(
            debug_on,
            f"""{TerminalColors.YELLOW}
            ======= DEBUG OUTPUT =======
            Updated User records:
            {updated_user_records}
            
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

        Returns the corresponding User object.
        """

        # Create some local variables to make data tracing easier
        contact_email = contact.email
        contact_first_name = contact.first_name
        contact_lastname = contact.last_name

        user_exists = User.objects.filter(contact=contact).exists()
        if user_exists:
            try:
                # ----------------------- UPDATE USER -----------------------
                # ---- GET THE USER
                target_user = User.objects.get(contact=contact)
                # DEBUG:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"""{TerminalColors.YELLOW}
                    > Found linked entry in User table for: {contact_first_name} {contact_lastname} {contact_email}
                    {TerminalColors.ENDC}""",  # noqa
                )

                # ---- UPDATE THE USER IF IT DOES NOT HAVE A FIRST AND LAST NAMES
                # ---- LET'S KEEP A LIGHT TOUCH
                if not target_user.first_name or not target_user.last_name:
                    target_user.first_name = contact_first_name
                    target_user.last_name = contact_lastname
                
                target_user.save()

                return (target_user)

            except Exception as E:
                logger.warning(
                    f"""
                    {TerminalColors.FAIL}
                    !!! ERROR: An exception occured in the
                    User table for the following user:
                    {contact_email}
                    ----------TERMINATING----------"""
                )
                sys.exit()

    # ======================================================
    # ================= PROCESS CONTACTS  ==================
    # ======================================================
    
    # C901 'Command.handle' is too complex
    def process_contacts(
        self,
        debug_on,
        skipped_user_entries,
        updated_user_entries,
        debug_max_entries_to_parse,
        total_rows_parsed,
    ):
        for contact in Contact.objects.all():
            # Create some local variables to make data tracing easier
            contact_email = contact.email
            contact_first_name = contact.first_name
            contact_last_name = contact.last_name

            # DEBUG:
            # TerminalHelper.print_conditional(
            #     debug_on,
            #     f"{TerminalColors.OKCYAN}"
            #     "Processing Contact: "
            #     f"{contact_email},"
            #     f" {contact_first_name},"
            #     f" {contact_last_name}"
            #     f"{TerminalColors.ENDC}",  # noqa
            # )

            # ======================================================
            # ====================== USER  =======================
            target_user = self.update_user(contact, debug_on)

            debug_string = ""
            if target_user:
                # ---------------- UPDATED ----------------
                updated_user_entries.append(contact.email)
                debug_string = f"updated user: {target_user}"
            else:
                skipped_user_entries.append(contact.email)
                debug_string = f"skipped user: {contact.email}"

            # DEBUG:
            # TerminalHelper.print_conditional(
            #     debug_on,
            #     (f"{TerminalColors.OKCYAN} {debug_string} {TerminalColors.ENDC}"),
            # )

            # ------------------ Parse limit reached? ------------------
            # Check parse limit and exit loop if parse limit has been reached
            if self.parse_limit_reached(debug_max_entries_to_parse, total_rows_parsed):
                break
        return (
            skipped_user_entries,
            updated_user_entries,
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
        debug_max_entries_to_parse = int(options.get("limitParse"))  # set to 0 to parse all entries

        self.print_debug_mode_statements(debug_on, debug_max_entries_to_parse)

        # users we UPDATED
        updated_user_entries = []

        # users we SKIPPED
        skipped_user_entries = []

        # if we are limiting our parse (for testing purposes, keep
        # track of total rows parsed)
        total_rows_parsed = 0

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
            skipped_user_entries,
            updated_user_entries,
        ) = self.process_contacts(
            debug_on,
            skipped_user_entries,
            updated_user_entries,
            debug_max_entries_to_parse,
            total_rows_parsed,
        )

        self.print_summary_of_findings(
            updated_user_entries,
            skipped_user_entries,
            debug_on,
        )
