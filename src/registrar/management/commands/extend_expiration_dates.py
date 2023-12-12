"""Data migration: Extends expiration dates for valid domains"""

import argparse
from datetime import date
import datetime
import logging

from django.core.management import BaseCommand
from epplibwrapper.errors import RegistryError
from registrar.models import Domain
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from datetime import datetime
try:
    from epplib.exceptions import TransportError
except ImportError:
    pass


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Extends expiration dates for valid domains"

    def __init__(self):
        """Sets global variables for code tidyness"""
        super().__init__()
        self.update_success = []
        self.update_skipped = []
        self.update_failed = []
        self.expiration_cutoff = date(2023, 11, 15)

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "--extensionAmount",
            type=int,
            default=1,
            help="Determines the period (in years) to extend expiration dates by",
        )
        parser.add_argument(
            "--limitParse",
            type=int,
            default=0,
            help="Sets a cap on the number of records to parse",
        )
        parser.add_argument(
            "--disableIdempotentCheck", action=argparse.BooleanOptionalAction, help="Disable script idempotence"
        )
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction, help="Increases log chattiness")

    def handle(self, **options):
        """
        Extends the expiration dates for valid domains.

        If a parse limit is set and it's less than the total number of valid domains,
        the number of domains to change is set to the parse limit.

        Includes an idempotence check.
        """

        # Retrieve command line options
        extension_amount = options.get("extensionAmount")
        limit_parse = options.get("limitParse")
        disable_idempotence = options.get("disableIdempotentCheck")
        debug = options.get("debug")

        # Does a check to see if parse_limit is a positive int.
        # Raise an error if not.
        self.check_if_positive_int(limit_parse, "limitParse")

        valid_domains = Domain.objects.filter(
            expiration_date__gte=self.expiration_cutoff, state=Domain.State.READY
        ).order_by("name")

        domains_to_change_count = valid_domains.count()
        if limit_parse != 0:
            domains_to_change_count = limit_parse
            valid_domains = valid_domains[:limit_parse]

        # Determines if we should continue code execution or not.
        # If the user prompts 'N', a sys.exit() will be called.
        self.prompt_user_to_proceed(extension_amount, domains_to_change_count)

        for domain in valid_domains:
            try:
                is_idempotent = self.idempotence_check(domain, extension_amount)
                if not disable_idempotence and not is_idempotent:
                    self.update_skipped.append(domain.name)
                    logger.info(f"{TerminalColors.YELLOW}" f"Skipping update for {domain}" f"{TerminalColors.ENDC}")
                else:
                    domain.renew_domain(extension_amount)
            # Catches registry errors. Failures indicate bad data, or a faulty connection.
            except (RegistryError, KeyError, TransportError) as err:
                self.update_failed.append(domain.name)
                logger.error(
                    f"{TerminalColors.FAIL}" f"Failed to update expiration date for {domain}" f"{TerminalColors.ENDC}"
                )
                logger.error(err)
            else:
                self.update_success.append(domain.name)
                logger.info(
                    f"{TerminalColors.OKCYAN}" f"Successfully updated expiration date for {domain}" f"{TerminalColors.ENDC}"
                )
            finally:
                self.log_script_run_summary(debug)

    # == Helper functions == #
    def idempotence_check(self, domain: Domain, extension_amount):
        """Determines if the proposed operation violates idempotency"""
        # Because our migration data had a hard stop date, we can determine if our change
        # is valid simply checking the date is within a valid range and it was updated
        # in epp on the current day.
        # CAVEAT: This check stops working a day after it is ran (for some domains) and
        # if the domain was updated by a user on the day it was ran. A more robust 
        # solution would be a db flag
        proposed_date = self.add_years(domain.registry_expiration_date, extension_amount)
        minimum_extension_date = self.add_years(self.expiration_cutoff, extension_amount)
        maximum_extension_date = self.add_years(date(2025, 12, 31), extension_amount)

        valid_range = minimum_extension_date <= proposed_date <= maximum_extension_date

        return valid_range

    def prompt_user_to_proceed(self, extension_amount, domains_to_change_count):
        """Asks if the user wants to proceed with this action"""
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Extension Amount==
            Period: {extension_amount} year(s)

            ==Proposed Changes==
            Domains to change: {domains_to_change_count}
            """,
            prompt_title="Do you wish to proceed?",
        )

        logger.info(f"{TerminalColors.MAGENTA}" "Preparing to extend expiration dates..." f"{TerminalColors.ENDC}")

    def check_if_positive_int(self, value: int, var_name: str):
        """
        Determines if the given integer value is positive or not.
        If not, it raises an ArgumentTypeError
        """
        if value < 0:
            raise argparse.ArgumentTypeError(
                f"{value} is an invalid integer value for {var_name}. " "Must be positive."
            )

        return value

    def log_script_run_summary(self, debug):
        """Prints success, failed, and skipped counts, as well as
        all affected domains."""
        update_success_count = len(self.update_success)
        update_failed_count = len(self.update_failed)
        update_skipped_count = len(self.update_skipped)

        # Prepare debug messages
        debug_messages = {
            "success": (f"{TerminalColors.OKCYAN}Updated these Domains: {self.update_success}{TerminalColors.ENDC}\n"),
            "skipped": (f"{TerminalColors.YELLOW}Skipped these Domains: {self.update_skipped}{TerminalColors.ENDC}\n"),
            "failed": (
                f"{TerminalColors.FAIL}Failed to update these Domains: {self.update_failed}{TerminalColors.ENDC}\n"
            ),
        }

        # Print out a list of everything that was changed, if we have any changes to log.
        # Otherwise, don't print anything.
        TerminalHelper.print_conditional(
            debug,
            f"{debug_messages.get('success') if update_success_count > 0 else ''}"
            f"{debug_messages.get('skipped') if update_skipped_count > 0 else ''}"
            f"{debug_messages.get('failed') if update_failed_count > 0 else ''}",
        )

        if update_failed_count == 0 and update_skipped_count == 0:
            logger.info(
                f"""{TerminalColors.OKGREEN}
                ============= FINISHED ===============
                Updated {update_success_count} Domain entries
                {TerminalColors.ENDC}
                """
            )
        elif update_failed_count == 0:
            logger.info(
                f"""{TerminalColors.YELLOW}
                ============= FINISHED ===============
                Updated {update_success_count} Domain entries

                ----- IDEMPOTENCY CHECK FAILED -----
                Skipped updating {update_skipped_count} Domain entries
                {TerminalColors.ENDC}
                """
            )
        else:
            logger.info(
                f"""{TerminalColors.FAIL}
                ============= FINISHED ===============
                Updated {update_success_count} Domain entries

                ----- UPDATE FAILED -----
                Failed to update {update_failed_count} Domain entries,
                Skipped updating {update_skipped_count} Domain entries
                {TerminalColors.ENDC}
                """
            )

    # We use this manual approach rather than relative delta due to our
    # github localenv not having the package installed.
    # Credit: https://stackoverflow.com/questions/15741618/add-one-year-in-current-date-python
    def add_years(self, old_date, years):
        """Return a date that's `years` years after the date (or datetime)
        object `old_date`. Return the same calendar date (month and day) in the
        destination year, if it exists, otherwise use the following day
        (thus changing February 29 to March 1).

        """
        try:
            return old_date.replace(year=old_date.year + years)
        except ValueError:
            return old_date + (date(old_date.year + years, 1, 1) - date(old_date.year, 1, 1))
