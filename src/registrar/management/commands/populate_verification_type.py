import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each valid User object and updates its verification_type value"

    def handle(self, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""
        filter_condition = {"verification_type__isnull": True}
        self.mass_update_records(User, filter_condition, ["verification_type"])

    def update_record(self, record: User):
        """Defines how we update the verification_type field"""
        record.set_user_verification_type()
        logger.info(
            f"{TerminalColors.OKCYAN}Updating {record} => " f"{record.verification_type}{TerminalColors.OKCYAN}"
        )
