import argparse
import logging
from typing import List
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper, ScriptDataHelper
from registrar.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Loops through each valid User object and updates its verification_type value"

    def handle(self, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""

        users = User.objects.filter(verification_type__isnull=True)

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Proposed Changes==
            Number of User objects to change: {len(users)}
            This field will be updated on each record: verification_type
            """,
            prompt_title="Do you wish to patch verification_type data?",
        )
        logger.info("Updating...")

        user_to_update: List[User] = []
        user_failed_to_update: List[User] = []
        for user in users:
            try:
                user.set_user_verification_type()
                user_to_update.append(user)
            except Exception as err:
                user_failed_to_update.append(user)
                logger.error(err)
                logger.error(f"{TerminalColors.FAIL}" f"Failed to update {user}" f"{TerminalColors.ENDC}")

        # Do a bulk update on the first_ready field
        ScriptDataHelper.bulk_update_fields(User, user_to_update, ["verification_type"])

        # Log what happened
        TerminalHelper.log_script_run_summary(user_to_update, user_failed_to_update, skipped=[], debug=True)
