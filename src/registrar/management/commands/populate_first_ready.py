import argparse
import logging
from django.core.paginator import Paginator
from typing import List

from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Loops through each valid Domain object and updates its first_created value"

    def __init__(self):
        super().__init__()
        self.to_update: List[Domain] = []
        self.failed_to_update: List[Domain] = []
        self.skipped: List[Domain] = []

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

    def handle(self, **kwargs):
        """Loops through each valid Domain object and updates its first_created value"""
        debug = kwargs.get("debug")
        valid_states = [Domain.State.READY, Domain.State.ON_HOLD, Domain.State.DELETED]
        domains = Domain.objects.filter(first_ready=None, state__in=valid_states)

        for domain in domains:
            try:
                self.update_first_ready_for_domain(domain, debug)
            except Exception as err:
                self.failed_to_update.append(domain)
                logger.error(err)
                logger.error(
                    f"{TerminalColors.FAIL}"
                    f"Failed to update {domain}"
                    f"{TerminalColors.ENDC}"
                )
        
        batch_size = 1000
        # Create a Paginator object. Bulk_update on the full dataset
        # is too memory intensive for our current app config, so we can chunk this data instead.
        paginator = Paginator(self.to_update, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            Domain.objects.bulk_update(page.object_list, ["first_ready"])

        self.log_script_run_summary(debug)

    def update_first_ready_for_domain(self, domain: Domain, debug: bool):
        """Grabs the created_at field and associates it with the first_ready column.
        Appends the result to the to_update list."""
        created_at = domain.created_at
        if created_at is not None:
            domain.first_ready = domain.created_at
            self.to_update.append(domain)
            if debug:
                logger.info(f"Updating {domain}")
        else:
            self.skipped.append(domain)
            if debug:
                logger.warning(f"Skipped updating {domain}")

    def log_script_run_summary(self, debug: bool):
        """Prints success, failed, and skipped counts, as well as
        all affected objects."""
        update_success_count = len(self.to_update)
        update_failed_count = len(self.failed_to_update)
        update_skipped_count = len(self.skipped)

        # Prepare debug messages
        debug_messages = {
            "success": (f"{TerminalColors.OKCYAN}Updated: {self.to_update}{TerminalColors.ENDC}\n"),
            "skipped": (f"{TerminalColors.YELLOW}Skipped: {self.skipped}{TerminalColors.ENDC}\n"),
            "failed": (f"{TerminalColors.FAIL}Failed: {self.failed_to_update}{TerminalColors.ENDC}\n"),
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
            logger.warning(
                f"""{TerminalColors.YELLOW}
                ============= FINISHED ===============
                Updated {update_success_count} Domain entries
                ----- SOME CREATED_AT DATA WAS NONE (NEEDS MANUAL PATCHING) -----
                Skipped updating {update_skipped_count} Domain entries
                {TerminalColors.ENDC}
                """
            )
        else:
            logger.error(
                f"""{TerminalColors.FAIL}
                ============= FINISHED ===============
                Updated {update_success_count} Domain entries
                ----- UPDATE FAILED -----
                Failed to update {update_failed_count} Domain entries,
                Skipped updating {update_skipped_count} Domain entries
                {TerminalColors.ENDC}
                """
            )