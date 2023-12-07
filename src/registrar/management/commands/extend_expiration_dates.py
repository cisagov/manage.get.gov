"""Data migration: Extends expiration dates for valid domains"""

import argparse
from datetime import date
import logging

from django.core.management import BaseCommand
from epplibwrapper.errors import RegistryError
from registrar.models import Domain
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from dateutil.relativedelta import relativedelta
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
        self.debug = False

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
            "--disableIdempotentCheck", 
            action=argparse.BooleanOptionalAction,
            help="Disable script idempotence"
        )
        parser.add_argument(
            "--debug", 
            action=argparse.BooleanOptionalAction,
            help="Increases log chattiness"
        )

    def handle(self, **options):
        """"""
        extension_amount = options.get("extensionAmount")
        limit_parse = options.get("limitParse")
        disable_idempotence = options.get("disableIdempotentCheck")
        self.debug = options.get("debug")

        # Does a check to see if parse_limit is a positive int.
        # Raise an error if not.
        self.check_if_positive_int(limit_parse, "limitParse")

        valid_domains = Domain.objects.filter(
            expiration_date__gte=date(2023, 11, 15),
            state=Domain.State.READY
        ).order_by("name")

        domains_to_change_count = valid_domains.count()
        if limit_parse != 0 and limit_parse < domains_to_change_count:
            domains_to_change_count = limit_parse

        # Determines if we should continue code execution or not.
        # If the user prompts 'N', a sys.exit() will be called.
        self.prompt_user_to_proceed(extension_amount, domains_to_change_count)

        for i, domain in enumerate(valid_domains):
            if limit_parse != 0 and i > limit_parse:
                break
            
            is_idempotent = self.idempotence_check(domain, extension_amount)
            if not disable_idempotence and not is_idempotent:
                self.update_skipped.append(domain.name)
            else:
                self.extend_expiration_date_on_domain(domain, extension_amount)
        
        self.log_script_run_summary()
    
    def extend_expiration_date_on_domain(self, domain: Domain, extension_amount: int):
        """
        Given a particular domain,
        extend the expiration date by the period specified in extension_amount
        """
        try:
            domain.renew_domain(extension_amount)
        except (RegistryError, TransportError) as err:
            logger.error(
                f"{TerminalColors.FAIL}"
                f"Failed to update expiration date for {domain}"
                f"{TerminalColors.ENDC}"
            )
            logger.error(err)
        except Exception as err:
            self.log_script_run_summary()
            raise err
        else:
            self.update_success.append(domain.name)
            logger.info(
                f"{TerminalColors.OKCYAN}"
                f"Successfully updated expiration date for {domain}"
                f"{TerminalColors.ENDC}"
            )

    # == Helper functions == #
    def idempotence_check(self, domain, extension_amount):
        """Determines if the proposed operation violates idempotency"""
        proposed_date = domain.expiration_date + relativedelta(years=extension_amount)
        # Because our migration data had a hard stop date, we can determine if our change
        # is valid simply checking if adding a year to our current date yields a greater date
        # than the proposed.
        # CAVEAT: This check stops working after a year has elapsed between when this script
        # was ran, and when it was ran again. This is good enough for now, but a more robust
        # solution would be a DB flag.
        is_idempotent = proposed_date < date.today() + relativedelta(years=extension_amount)
        return is_idempotent

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
            prompt_title="Do you wish to modify Expiration Dates for the given Domains?",
        )

        logger.info(
            f"{TerminalColors.MAGENTA}"
            "Preparing to extend expiration dates..."
            f"{TerminalColors.ENDC}"
        )

    def log_script_run_summary(self):
        """Prints success, failed, and skipped counts, as well as 
        all affected domains."""
        update_success_count = len(self.update_success)
        update_failed_count = len(self.update_failed)
        update_skipped_count = len(self.update_skipped)
        if update_failed_count == 0 and update_skipped_count == 0:
            logger.info(
                f"""{TerminalColors.OKGREEN}
                ============= FINISHED ===============
                Updated {update_success_count} Domain entries
                {TerminalColors.ENDC}
                """
            )
            TerminalHelper.print_conditional(
                self.debug,
                f"""
                {TerminalColors.OKGREEN}
                Updated the following Domains: {self.update_success}
                {TerminalColors.ENDC}
                """,
            )
        elif update_failed_count == 0:
            TerminalHelper.print_conditional(
                self.debug,
                f"""
                {TerminalColors.OKGREEN}
                Updated the following Domains: {self.update_success}
                {TerminalColors.ENDC}

                {TerminalColors.YELLOW}
                Skipped the following Domains: {self.update_skipped}
                {TerminalColors.ENDC}
                """,
            )
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
            TerminalHelper.print_conditional(
                self.debug,
                f"""
                {TerminalColors.OKGREEN}
                Updated the following Domains: {self.update_success}
                {TerminalColors.ENDC}

                {TerminalColors.YELLOW}
                Skipped the following Domains: {self.update_skipped}
                {TerminalColors.ENDC}

                {TerminalColors.FAIL}
                Failed to update the following Domains: {self.update_failed}
                {TerminalColors.ENDC}
                """,
            )
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

    
    def check_if_positive_int(self, value: int, var_name: str):
        """
        Determines if the given integer value is positive or not. 
        If not, it raises an ArgumentTypeError
        """
        if value < 0:
            raise argparse.ArgumentTypeError(
                f"{value} is an invalid integer value for {var_name}. " 
                "Must be positive."
            )

        return value