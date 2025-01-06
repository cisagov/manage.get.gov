import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors, TerminalHelper
from registrar.models import DomainRequest
from registrar.models.utility.generic_helper import normalize_string

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each domain request object and populates requested suborg info"

    def handle(self, **kwargs):
        """Loops through each DomainRequest object and populates
        its last_status_update and first_submitted_date values"""
        filter_conditions = {
            "portfolio__isnull": False,
            "organization_name__isnull": False,
            "sub_organization__isnull": True,
            "portfolio__organization_name__isnull": False,
        }
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

    def should_skip_record(self, record) -> bool:
        """Skips updating the record if the portfolio name is the same as the org name,
        or if we are trying to update a record in an invalid status."""
        invalid_statuses = [
            DomainRequest.DomainRequestStatus.APPROVED,
            DomainRequest.DomainRequestStatus.REJECTED,
            DomainRequest.DomainRequestStatus.INELIGIBLE,
            DomainRequest.DomainRequestStatus.STARTED,
        ]
        if record.status in invalid_statuses:
            return True

        portfolio_normalized = normalize_string(record.portfolio.organization_name)
        org_normalized = normalize_string(record.organization_name)
        if portfolio_normalized == org_normalized:
            return True

        return False
