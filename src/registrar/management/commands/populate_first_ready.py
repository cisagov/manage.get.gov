import argparse
import logging
from django.core.paginator import Paginator
from typing import List
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper, ScriptDataHelper
from registrar.models import Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Loops through each valid Domain object and updates its first_created value"

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

    def handle(self, **kwargs):
        """Loops through each valid Domain object and updates its first_created value"""
        debug = kwargs.get("debug")
        valid_states = [Domain.State.READY, Domain.State.ON_HOLD, Domain.State.DELETED]
        domains = Domain.objects.filter(first_ready=None, state__in=valid_states)

        # Keep track of what we want to update, what failed, and what was skipped
        to_update: List[Domain] = []
        failed_to_update: List[Domain] = []
        skipped: List[Domain] = []

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
                update_first_ready_for_domain(domain, debug)
            except Exception as err:
                failed_to_update.append(domain)
                logger.error(err)
                logger.error(
                    f"{TerminalColors.FAIL}"
                    f"Failed to update {domain}"
                    f"{TerminalColors.ENDC}"
                )
        ScriptDataHelper.bulk_update_fields(Domain, to_update, ["first_ready"])

        # Log what happened
        TerminalHelper.log_script_run_summary(
            to_update, failed_to_update, skipped, debug
        )
