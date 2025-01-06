import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors, TerminalHelper
from registrar.models import DomainRequest

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each domain request object and populates requested suborg info"

    def handle(self, **kwargs):
        """Loops through each DomainRequest object and populates
        its last_status_update and first_submitted_date values"""
        filter_conditions = {"portfolio__isnull": False, "sub_organization__isnull": True}
        fields_to_update = ["requested_suborganization", "suborganization_city", "suborganization_state_territory"]
        self.mass_update_records(DomainRequest, filter_conditions, fields_to_update)

    def update_record(self, record: DomainRequest):
        """Adds data to requested_suborganization, suborganization_city, and suborganization_state_territory."""
        record.requested_suborganization = record.organization_name
        record.suborganization_city = record.city
        record.suborganization_state_territory = record.state_territory
        message = (
            f"Updating {record} => requested_suborg: {record.organization_name}, "
            f"sub_city: {record.city}, suborg_state_territory: {record.state_territory}."
        )
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKBLUE, message)
