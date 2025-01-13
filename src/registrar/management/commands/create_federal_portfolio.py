"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User
from registrar.models.utility.generic_helper import normalize_string


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates a federal portfolio given a FederalAgency name"

    def __init__(self, *args, **kwargs):
        """Defines fields to track what portfolios were updated, skipped, or just outright failed."""
        super().__init__(*args, **kwargs)
        self.updated_portfolios = set()
        self.skipped_portfolios = set()
        self.failed_portfolios = set()

    def add_arguments(self, parser):
        """Add command line arguments to create federal portfolios.

        Required (mutually exclusive) arguments:
            --agency_name: Name of a specific FederalAgency to create a portfolio for
            --branch: Federal branch to process ("executive", "legislative", or "judicial"). 
                    Creates portfolios for all FederalAgencies in that branch.

        Required (at least one):
            --parse_requests: Add the created portfolio(s) to related DomainRequest records
            --parse_domains: Add the created portfolio(s) to related DomainInformation records  
            Note: You can use both --parse_requests and --parse_domains together

        Optional (mutually exclusive with parse options):
            --both: Shorthand for using both --parse_requests and --parse_domains
                Cannot be used with --parse_requests or --parse_domains
        """
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--agency_name",
            help="The name of the FederalAgency to add",
        )
        group.add_argument(
            "--branch",
            choices=["executive", "legislative", "judicial"],
            help="The federal branch to process. Creates a portfolio for each FederalAgency in this branch.",
        )
        parser.add_argument(
            "--parse_requests",
            action=argparse.BooleanOptionalAction,
            help="Adds portfolio to DomainRequests",
        )
        parser.add_argument(
            "--parse_domains",
            action=argparse.BooleanOptionalAction,
            help="Adds portfolio to DomainInformation",
        )
        parser.add_argument(
            "--both",
            action=argparse.BooleanOptionalAction,
            help="Adds portfolio to both requests and domains",
        )

    def handle(self, **options):
        agency_name = options.get("agency_name")
        branch = options.get("branch")
        parse_requests = options.get("parse_requests")
        parse_domains = options.get("parse_domains")
        both = options.get("both")

        if not both:
            if not parse_requests and not parse_domains:
                raise CommandError("You must specify at least one of --parse_requests or --parse_domains.")
        else:
            if parse_requests or parse_domains:
                raise CommandError("You cannot pass --parse_requests or --parse_domains when passing --both.")

        federal_agency_filter = {"agency__iexact": agency_name} if agency_name else {"federal_type": branch}
        agencies = FederalAgency.objects.filter(**federal_agency_filter)
        if not agencies or agencies.count() < 1:
            if agency_name:
                raise CommandError(
                    f"Cannot find the federal agency '{agency_name}' in our database. "
                    "The value you enter for `agency_name` must be "
                    "prepopulated in the FederalAgency table before proceeding."
                )
            else:
                raise CommandError(f"Cannot find '{branch}' federal agencies in our database.")

        portfolios = []
        for federal_agency in agencies:
            message = f"Processing federal agency '{federal_agency.agency}'..."
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
            try:
                # C901 'Command.handle' is too complex (12)
                portfolio = self.handle_populate_portfolio(federal_agency, parse_domains, parse_requests, both)
                portfolios.append(portfolio)
            except Exception as exec:
                self.failed_portfolios.add(federal_agency)
                logger.error(exec)
                message = f"Failed to create portfolio '{federal_agency.agency}'"
                TerminalHelper.colorful_logger(logger.info, TerminalColors.FAIL, message)

        TerminalHelper.log_script_run_summary(
            self.updated_portfolios,
            self.failed_portfolios,
            self.skipped_portfolios,
            debug=False,
            skipped_header="----- SOME PORTFOLIOS WERE SKIPPED -----",
            display_as_str=True,
        )

        # POST PROCESSING STEP: Remove the federal agency if it matches the portfolio name.
        # We only do this for started domain requests.
        if parse_requests or both:
            TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=True,
                prompt_message="This action will update domain requests even if they aren't on a portfolio.",
                prompt_title=(
                    "POST PROCESS STEP: Do you want to clear federal agency on (related) started domain requests?"
                ),
                verify_message=None,
            )
            self.post_process_started_domain_requests(agencies, portfolios)

    def post_process_started_domain_requests(self, agencies, portfolios):
        """
        Removes duplicate organization data by clearing federal_agency when it matches the portfolio name.
        Only processes domain requests in STARTED status.
        """
        message = "Removing duplicate portfolio and federal_agency values from domain requests..."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

        # For each request, clear the federal agency under these conditions:
        # 1. A portfolio *already exists* with the same name as the federal agency.
        # 2. Said portfolio (or portfolios) are only the ones specified at the start of the script.
        # 3. The domain request is in status "started".
        # Note: Both names are normalized so excess spaces are stripped and the string is lowercased.
        domain_requests_to_update = DomainRequest.objects.filter(
            federal_agency__in=agencies,
            federal_agency__agency__isnull=False,
            status=DomainRequest.DomainRequestStatus.STARTED,
            organization_name__isnull=False,
        )
        portfolio_set = {normalize_string(portfolio.organization_name) for portfolio in portfolios if portfolio}

        # Update the request, assuming the given agency name matches the portfolio name
        updated_requests = []
        for req in domain_requests_to_update:
            agency_name = normalize_string(req.federal_agency.agency)
            if agency_name in portfolio_set:
                req.federal_agency = None
                updated_requests.append(req)

        # Execute the update and Log the results
        if TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=False,
            prompt_message=(
                f"{len(domain_requests_to_update)} domain requests will be updated. "
                f"These records will be changed: {[str(req) for req in updated_requests]}"
            ),
            prompt_title="Do wish to commit this update to the database?",
        ):
            DomainRequest.objects.bulk_update(updated_requests, ["federal_agency"])
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKBLUE, "Action completed successfully.")

    def handle_populate_portfolio(self, federal_agency, parse_domains, parse_requests, both):
        """Attempts to create a portfolio. If successful, this function will
        also create new suborganizations.
        Returns the portfolio for the given federal_agency.
        """
        portfolio, created = self.create_portfolio(federal_agency)
        if created:
            self.create_suborganizations(portfolio, federal_agency)
            if parse_domains or both:
                self.handle_portfolio_domains(portfolio, federal_agency)

        if parse_requests or both:
            self.handle_portfolio_requests(portfolio, federal_agency)

        return portfolio

    def create_portfolio(self, federal_agency):
        """Creates a portfolio if it doesn't presently exist.
        Returns portfolio, created."""
        # Get the org name / senior official
        org_name = federal_agency.agency
        so = federal_agency.so_federal_agency.first() if federal_agency.so_federal_agency.exists() else None

        # First just try to get an existing portfolio
        portfolio = Portfolio.objects.filter(organization_name=org_name).first()
        if portfolio:
            self.skipped_portfolios.add(portfolio)
            TerminalHelper.colorful_logger(
                logger.info,
                TerminalColors.YELLOW,
                f"Portfolio with organization name '{org_name}' already exists. Skipping create.",
            )
            return portfolio, False

        # Create new portfolio if it doesn't exist
        portfolio = Portfolio.objects.create(
            organization_name=org_name,
            federal_agency=federal_agency,
            organization_type=DomainRequest.OrganizationChoices.FEDERAL,
            creator=User.get_default_user(),
            notes="Auto-generated record",
            senior_official=so,
        )

        self.updated_portfolios.add(portfolio)
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, f"Created portfolio '{portfolio}'")

        # Log if the senior official was added or not.
        if portfolio.senior_official:
            message = f"Added senior official '{portfolio.senior_official}'"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
        else:
            message = (
                f"No senior official added to portfolio '{org_name}'. "
                "None was returned for the reverse relation `FederalAgency.so_federal_agency.first()`"
            )
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)

        return portfolio, True

    def create_suborganizations(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """Create Suborganizations tied to the given portfolio based on DomainInformation objects"""
        valid_agencies = DomainInformation.objects.filter(
            federal_agency=federal_agency, organization_name__isnull=False
        )
        org_names = set(valid_agencies.values_list("organization_name", flat=True))

        if not org_names:
            message = (
                "Could not add any suborganizations."
                f"\nNo suborganizations were found for '{federal_agency}' when filtering on this name, "
                "and excluding null organization_name records."
            )
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.FAIL, message)
            return

        # Check for existing suborgs on the current portfolio
        existing_suborgs = Suborganization.objects.filter(name__in=org_names, name__isnull=False)
        if existing_suborgs.exists():
            message = f"Some suborganizations already exist for portfolio '{portfolio}'."
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKBLUE, message)

        # Create new suborgs, as long as they don't exist in the db already
        new_suborgs = []
        for name in org_names - set(existing_suborgs.values_list("name", flat=True)):
            if normalize_string(name) == normalize_string(portfolio.organization_name):
                # You can use this to populate location information, when this occurs.
                # However, this isn't needed for now so we can skip it.
                message = (
                    f"Skipping suborganization create on record '{name}'. "
                    "The federal agency name is the same as the portfolio name."
                )
                TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, message)
            else:
                new_suborgs.append(Suborganization(name=name, portfolio=portfolio))  # type: ignore

        if new_suborgs:
            Suborganization.objects.bulk_create(new_suborgs)
            TerminalHelper.colorful_logger(
                logger.info, TerminalColors.OKGREEN, f"Added {len(new_suborgs)} suborganizations"
            )
        else:
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, "No suborganizations added")

    def handle_portfolio_requests(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domain requests for a federal agency.
        Updates all relevant domain request records.
        """
        invalid_states = [
            DomainRequest.DomainRequestStatus.STARTED,
            DomainRequest.DomainRequestStatus.INELIGIBLE,
            DomainRequest.DomainRequestStatus.REJECTED,
        ]
        domain_requests = DomainRequest.objects.filter(federal_agency=federal_agency, portfolio__isnull=True).exclude(
            status__in=invalid_states
        )
        if not domain_requests.exists():
            message = f"""
            Portfolio '{portfolio}' not added to domain requests: no valid records found.
            This means that a filter on DomainInformation for the federal_agency '{federal_agency}' returned no results.
            Excluded statuses: STARTED, INELIGIBLE, REJECTED.
            Filter info: DomainRequest.objects.filter(federal_agency=federal_agency, portfolio__isnull=True).exclude(
                status__in=invalid_states
            )
            """
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return None

        # Get all suborg information and store it in a dict to avoid doing a db call
        suborgs = Suborganization.objects.filter(portfolio=portfolio).in_bulk(field_name="name")
        for domain_request in domain_requests:
            # Set the portfolio
            domain_request.portfolio = portfolio

            # Set suborg info
            domain_request.sub_organization = suborgs.get(domain_request.organization_name, None)
            if domain_request.sub_organization is None:
                domain_request.requested_suborganization = normalize_string(
                    domain_request.organization_name, lowercase=False
                )
                domain_request.suborganization_city = normalize_string(domain_request.city, lowercase=False)
                domain_request.suborganization_state_territory = domain_request.state_territory

            self.updated_portfolios.add(portfolio)

        DomainRequest.objects.bulk_update(
            domain_requests,
            [
                "portfolio",
                "sub_organization",
                "requested_suborganization",
                "suborganization_city",
                "suborganization_state_territory",
            ],
        )
        message = f"Added portfolio '{portfolio}' to {len(domain_requests)} domain requests."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domains for a federal agency.
        Updates all relevant domain information records.

        Returns a queryset of DomainInformation objects, or None if nothing changed.
        """
        domain_infos = DomainInformation.objects.filter(federal_agency=federal_agency, portfolio__isnull=True)
        if not domain_infos.exists():
            message = f"""
            Portfolio '{portfolio}' not added to domains: no valid records found.
            The filter on DomainInformation for the federal_agency '{federal_agency}' returned no results.
            Filter info: DomainInformation.objects.filter(federal_agency=federal_agency, portfolio__isnull=True)
            """
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return None

        # Get all suborg information and store it in a dict to avoid doing a db call
        suborgs = Suborganization.objects.filter(portfolio=portfolio).in_bulk(field_name="name")
        for domain_info in domain_infos:
            domain_info.portfolio = portfolio
            domain_info.sub_organization = suborgs.get(domain_info.organization_name, None)

        DomainInformation.objects.bulk_update(domain_infos, ["portfolio", "sub_organization"])
        message = f"Added portfolio '{portfolio}' to {len(domain_infos)} domains."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
