import argparse
import logging
from typing import List
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper, ScriptDataHelper
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
        # Get all valid domains
        valid_states = [Domain.State.READY, Domain.State.ON_HOLD, Domain.State.DELETED]
        domains = Domain.objects.filter(first_ready=None, state__in=valid_states)

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Proposed Changes==
            Number of Domain objects to change: {len(domains)}
            """,
            prompt_title="Do you wish to patch first_ready data?",
        )
        logger.info("Updating...")

        for domain in domains:
            try:
                self.update_first_ready_for_domain(domain, debug)
            except Exception as err:
                self.failed_to_update.append(domain)
                logger.error(err)
                logger.error(f"{TerminalColors.FAIL}" f"Failed to update {domain}" f"{TerminalColors.ENDC}")

        # Do a bulk update on the first_ready field
        ScriptDataHelper.bulk_update_fields(Domain, self.to_update, ["first_ready"])

        # Log what happened
        TerminalHelper.log_script_run_summary(self.to_update, self.failed_to_update, self.skipped, debug)

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
