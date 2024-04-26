import logging
from typing import List
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each valid User object and updates its verification_type value"

    def handle(self, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""
        filter_condition = {"verification_type__isnull": True}
        self.mass_populate_field(User, filter_condition, ["verification_type"])

    def populate_field(self, field_to_update):
        """Defines how we update the verification_type field"""
        field_to_update.set_user_verification_type()
        logger.info(
            f"{TerminalColors.OKCYAN}Updating {field_to_update} => "
            f"{field_to_update.verification_type}{TerminalColors.OKCYAN}"
        )
