import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import DomainRequest

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each valid domain request object and populates the last_status_update and first_submitted_date"

    def handle(self, **kwargs):
        """Loops through each valid DomainRequest object and populates its last_status_update and first_submitted_date values"""
        self.mass_update_records(DomainRequest, ["last_status_update", "last_submitted_date"])

    def update_record(self, record: DomainRequest):
        """Defines how we update the first_submitted_date and last_status_update fields"""
        record.set_dates()
        logger.info(
            f"{TerminalColors.OKCYAN}Updating {record} => first submitted date: " f"{record.first_submitted_date}{TerminalColors.OKCYAN}, last status update:" f"{record.last_status_update}{TerminalColors.OKCYAN}"
        )
