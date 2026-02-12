import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import FederalAgency, DomainInformation
from registrar.utility.constants import BranchChoices

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    """
    This command uses the PopulateScriptTemplate,
    which provides reusable logging and bulk updating functions for mass-updating fields.
    """

    help = "Loops through each valid User object and updates its verification_type value"
    prompt_title = "Do you wish to update all Federal Agencies?"

    def handle(self, **kwargs):
        """Loops through each valid User object and updates the value of its verification_type field"""

        # These are federal agencies that we don't have any data on.
        # Independent agencies are considered "EXECUTIVE" here.
        self.missing_records = {
            "Christopher Columbus Fellowship Foundation": BranchChoices.EXECUTIVE,
            "Commission for the Preservation of America's Heritage Abroad": BranchChoices.EXECUTIVE,
            "Commission of Fine Arts": BranchChoices.EXECUTIVE,
            "Committee for Purchase From People Who Are Blind or Severely Disabled": BranchChoices.EXECUTIVE,
            "DC Court Services and Offender Supervision Agency": BranchChoices.EXECUTIVE,
            "DC Pre-trial Services": BranchChoices.EXECUTIVE,
            "Department of Agriculture": BranchChoices.EXECUTIVE,
            "Dwight D. Eisenhower Memorial Commission": BranchChoices.LEGISLATIVE,
            "Farm Credit System Insurance Corporation": BranchChoices.EXECUTIVE,
            "Federal Financial Institutions Examination Council": BranchChoices.EXECUTIVE,
            "Federal Judiciary": BranchChoices.JUDICIAL,
            "Institute of Peace": BranchChoices.EXECUTIVE,
            "International Boundary and Water Commission: United States and Mexico": BranchChoices.EXECUTIVE,
            "International Boundary Commission: United States and Canada": BranchChoices.EXECUTIVE,
            "International Joint Commission: United States and Canada": BranchChoices.EXECUTIVE,
            "Legislative Branch": BranchChoices.LEGISLATIVE,
            "National Foundation on the Arts and the Humanities": BranchChoices.EXECUTIVE,
            "Nuclear Safety Oversight Committee": BranchChoices.EXECUTIVE,
            "Office of Compliance": BranchChoices.LEGISLATIVE,
            "Overseas Private Investment Corporation": BranchChoices.EXECUTIVE,
            "Public Defender Service for the District of Columbia": BranchChoices.EXECUTIVE,
            "The Executive Office of the President": BranchChoices.EXECUTIVE,
            "U.S. Access Board": BranchChoices.EXECUTIVE,
            "U.S. Agency for Global Media": BranchChoices.EXECUTIVE,
            "U.S. China Economic and Security Review Commission": BranchChoices.LEGISLATIVE,
            "U.S. Interagency Council on Homelessness": BranchChoices.EXECUTIVE,
            "U.S. International Trade Commission": BranchChoices.EXECUTIVE,
            "U.S. Postal Service": BranchChoices.EXECUTIVE,
            "U.S. Trade and Development Agency": BranchChoices.EXECUTIVE,
            "Udall Foundation": BranchChoices.EXECUTIVE,
            "United States Arctic Research Commission": BranchChoices.EXECUTIVE,
            "Utah Reclamation Mitigation and Conservation Commission": BranchChoices.EXECUTIVE,
            "Vietnam Education Foundation": BranchChoices.EXECUTIVE,
            "Woodrow Wilson International Center for Scholars": BranchChoices.EXECUTIVE,
            "World War I Centennial Commission": BranchChoices.EXECUTIVE,
        }
        # Get all existing domain requests. Select_related allows us to skip doing db queries.
        self.all_domain_infos = DomainInformation.objects.select_related("federal_agency")
        self.mass_update_records(
            FederalAgency, filter_conditions={"agency__isnull": False}, fields_to_update=["federal_type"]
        )

    def update_record(self, record: FederalAgency):
        """Defines how we update the federal_type field on each record."""
        request = self.all_domain_infos.filter(federal_agency__agency=record.agency).first()
        if request:
            record.federal_type = request.federal_type
        elif not request and record.agency in self.missing_records:
            record.federal_type = self.missing_records.get(record.agency)
        logger.info(f"{TerminalColors.OKCYAN}Updating {str(record)} => {record.federal_type}{TerminalColors.ENDC}")

    def should_skip_record(self, record) -> bool:  # noqa
        """Defines the conditions in which we should skip updating a record."""
        requests = self.all_domain_infos.filter(federal_agency__agency=record.agency, federal_type__isnull=False)
        # Check if all federal_type values are the same. Skip the record otherwise.
        distinct_federal_types = requests.values("federal_type").distinct()
        should_skip = distinct_federal_types.count() != 1
        if should_skip and record.agency not in self.missing_records:
            logger.info(
                f"{TerminalColors.YELLOW}Skipping update for {str(record)} => count is "
                f"{distinct_federal_types.count()} and records are {distinct_federal_types}{TerminalColors.ENDC}"
            )
        elif record.agency in self.missing_records:
            logger.info(
                f"{TerminalColors.MAGENTA}Missing data on {str(record)} - "
                f"swapping to manual mapping{TerminalColors.ENDC}"
            )
            should_skip = False
        return should_skip
