import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import FederalAgency, DomainInformation


logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    """
    This command uses the PopulateScriptTemplate.
    This template handles logging and bulk updating for you, for repetitive scripts that update a few fields.
    It is the ultimate lazy mans shorthand. Don't use this for anything terribly complicated.
    """

    help = "Loops through each valid User object and updates its verification_type value"
    prompt_title = "Do you wish to update all Federal Agencies?"
    display_run_summary_items_as_str = True

    def handle(self, **kwargs):
        """Loops through each valid User object and updates the value of its verification_type field"""

        # Get all existing domain requests. Select_related allows us to skip doing db queries.
        self.all_domain_infos = DomainInformation.objects.select_related("federal_agency")
        self.mass_update_records(
            FederalAgency, filter_conditions={"agency__isnull": False}, fields_to_update=["federal_type"]
        )

    def update_record(self, record: FederalAgency):
        """Defines how we update the federal_type field on each record."""
        request = self.all_domain_infos.filter(federal_agency__agency=record.agency).first()
        record.federal_type = request.federal_type
        logger.info(f"{TerminalColors.OKCYAN}Updating {str(record)} => {record.federal_type}{TerminalColors.ENDC}")

    def should_skip_record(self, record) -> bool:  # noqa
        """Defines the conditions in which we should skip updating a record."""
        requests = self.all_domain_infos.filter(federal_agency__agency=record.agency, federal_type__isnull=False)
        # Check if all federal_type values are the same. Skip the record otherwise.
        distinct_federal_types = requests.values("federal_type").distinct()
        should_skip = distinct_federal_types.count() != 1
        if should_skip:
            logger.info(
                f"{TerminalColors.YELLOW}Skipping update for {str(record)} => count is "
                f"{distinct_federal_types.count()} and records are {distinct_federal_types}{TerminalColors.ENDC}"
            )
        return should_skip
