""""""
import argparse
import logging

from typing import List

from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from django.db.models import Q

from registrar.models.transition_domain import TransitionDomain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the cat command on files from /tmp into the getgov directory."

    def __init__(self):
        super().__init__()
        self.di_to_update: List[DomainInformation] = []

        # Stores the domain_name for logging purposes
        self.di_failed_to_update: List[str] = []
        self.di_skipped: List[str] = []

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

    def handle(self, **options):
        debug = options.get("debug")

        # Update the "federal_agency" field
        self.patch_agency_info(debug)

    def patch_agency_info(self, debug):
        domain_info_to_fix = DomainInformation.objects.filter(Q(federal_agency=None) | Q(federal_agency=""))

        domain_names = domain_info_to_fix.values_list('domain__name', flat=True)
        transition_domains = TransitionDomain.objects.filter(domain_name__in=domain_names)
        
        # Get the domain names from TransitionDomain
        td_agencies = transition_domains.values_list("domain_name", "federal_agency").distinct()

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Proposed Changes==
            Number of DomainInformation objects to change: {len(td_agencies)}
            The following DomainInformation objects will be modified: {td_agencies}
            """,
            prompt_title="Do you wish to patch federal_agency data?",
        )
        logger.info("Updating...")

        # Create a dictionary mapping of domain_name to federal_agency
        td_dict = dict(td_agencies)

        for di in domain_info_to_fix:
            domain_name = di.domain.name
            federal_agency = td_dict.get(domain_name)

            # If agency exists on a TransitionDomain, update the related DomainInformation object
            if domain_name in td_dict and federal_agency is not None:
                di.federal_agency = federal_agency
                self.di_to_update.append(di)
                log_message = f"{TerminalColors.OKCYAN}Updated {di}{TerminalColors.ENDC}"
            else:
                self.di_skipped.append(di)
                log_message = f"{TerminalColors.YELLOW}Skipping update for {di}{TerminalColors.ENDC}"
            
            # Log the action if debug mode is on
            if debug:
                logger.info(log_message)

        # Bulk update the federal agency field in DomainInformation objects
        DomainInformation.objects.bulk_update(self.di_to_update, ["federal_agency"])

        # Get a list of each domain we changed
        corrected_domains = DomainInformation.objects.filter(domain__name__in=domain_names)

        # After the update has happened, do a sweep of what we get back.
        # If the fields we expect to update are still None, then something is wrong.
        for di in corrected_domains:
            if domain_name in td_dict and td_dict.get(domain_name) is None:
                logger.info(
                    f"{TerminalColors.FAIL}Failed to update {di}{TerminalColors.ENDC}"
                )
                self.di_failed_to_update.append(di)
        
        # === Log results and return data === #
        self.log_script_run_summary(debug)

    def log_script_run_summary(self, debug):
        """Prints success, failed, and skipped counts, as well as
        all affected objects."""
        update_success_count = len(self.di_to_update)
        update_failed_count = len(self.di_failed_to_update)
        update_skipped_count = len(self.di_skipped)

        # Prepare debug messages
        debug_messages = {
            "success": (f"{TerminalColors.OKCYAN}Updated: {self.di_to_update}{TerminalColors.ENDC}\n"),
            "skipped": (f"{TerminalColors.YELLOW}Skipped: {self.di_skipped}{TerminalColors.ENDC}\n"),
            "failed": (
                f"{TerminalColors.FAIL}Failed: {self.di_failed_to_update}{TerminalColors.ENDC}\n"
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
                Updated {update_success_count} DomainInformation entries
                {TerminalColors.ENDC}
                """
            )
        elif update_failed_count == 0:
            logger.info(
                f"""{TerminalColors.YELLOW}
                ============= FINISHED ===============
                Updated {update_success_count} DomainInformation entries

                ----- SOME AGENCY DATA WAS NONE (NEEDS MANUAL PATCHING) -----
                Skipped updating {update_skipped_count} DomainInformation entries
                {TerminalColors.ENDC}
                """
            )
        else:
            logger.info(
                f"""{TerminalColors.FAIL}
                ============= FINISHED ===============
                Updated {update_success_count} DomainInformation entries

                ----- UPDATE FAILED -----
                Failed to update {update_failed_count} DomainInformation entries,
                Skipped updating {update_skipped_count} DomainInformation entries
                {TerminalColors.ENDC}
                """
            )