"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User
from django.db.models import F

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
        """Add three arguments:
        1. agency_name => the value of FederalAgency.agency
        2. --parse_requests => if true, adds the given portfolio to each related DomainRequest
        3. --parse_domains => if true, adds the given portfolio to each related DomainInformation
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

        # C901 'Command.handle' is too complex (12)
        self.handle_all_populate_portfolio(agencies, parse_domains, parse_requests, both)
        TerminalHelper.log_script_run_summary(
            self.updated_portfolios,
            self.failed_portfolios,
            self.skipped_portfolios,
            debug=False,
            skipped_header="----- SOME PORTFOLIOS WERENT CREATED -----",
            display_as_str=True,
        )

    def handle_all_populate_portfolio(self, agencies, parse_domains, parse_requests, both):
        """Loops through every agency and creates a portfolio for each.
        For a given portfolio, it adds suborgs, and associates
        the suborg and portfolio to domains and domain requests.
        """
        all_suborganizations = []
        all_domains = []
        all_domain_requests = []
        for federal_agency in agencies:
            message = f"Processing federal agency '{federal_agency.agency}'..."
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
            # try:
            portfolio, created = self.create_portfolio(federal_agency)
            suborganizations = self.create_suborganizations(portfolio, federal_agency)
            domains = []
            domain_requests = []
            if created and parse_domains or both:
                domains = self.handle_portfolio_domains(portfolio, federal_agency)

            if parse_requests or both:
                domain_requests = self.handle_portfolio_requests(portfolio, federal_agency)

            all_suborganizations.extend(suborganizations)
            all_domains.extend(domains)
            all_domain_requests.extend(domain_requests)
            # except Exception as exec:
            #     self.failed_portfolios.add(federal_agency)
            #     logger.error(exec)
            #     message = f"Failed to create portfolio '{federal_agency.agency}'"
            #     TerminalHelper.colorful_logger(logger.info, TerminalColors.FAIL, message)

        # Post process steps
        # Add suborg info to created or existing suborgs.
        if all_suborganizations:
            updated_suborg_count = self.post_process_suborganization_fields(all_suborganizations, all_domains, all_domain_requests)
            message = f"Added city and state_territory information to {updated_suborg_count} suborgs."
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

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
        existing_suborgs = Suborganization.objects.filter(name__in=org_names)
        if existing_suborgs.exists():
            message = f"Some suborganizations already exist for portfolio '{portfolio}'."
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKBLUE, message)

        # Create new suborgs, as long as they don't exist in the db already
        new_suborgs = []
        for name in org_names - set(existing_suborgs.values_list("name", flat=True)):
            # Stored in variables due to linter wanting type information here.
            portfolio_name: str = portfolio.organization_name if portfolio.organization_name is not None else ""
            if name is not None and name.lower() == portfolio_name.lower():
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

        return new_suborgs

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
            domain_request.portfolio = portfolio
            if domain_request.organization_name in suborgs:
                domain_request.sub_organization = suborgs.get(domain_request.organization_name)
            self.updated_portfolios.add(portfolio)

        DomainRequest.objects.bulk_update(domain_requests, ["portfolio", "sub_organization"])
        message = f"Added portfolio '{portfolio}' to {len(domain_requests)} domain requests."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

        return list(domain_requests) if len(domain_requests) > 0 else []

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domains for a federal agency.
        Updates all relevant domain information records.
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
            if domain_info.organization_name in suborgs:
                domain_info.sub_organization = suborgs.get(domain_info.organization_name)

        DomainInformation.objects.bulk_update(domain_infos, ["portfolio", "sub_organization"])
        message = f"Added portfolio '{portfolio}' to {len(domain_infos)} domains."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

        return list(domain_infos) if len(domain_infos) > 0 else []

    def post_process_suborganization_fields(self, suborganizations, domains, requests):
        """Post-process suborganization fields by pulling data from related domains and requests.

        This function updates suborganization city and state_territory fields based on
        related domain information and domain request information.
        """
        domains = DomainInformation.objects.filter(id__in=[domain.id for domain in domains]).exclude(
            portfolio__isnull=True,
            organization_name__isnull=True,
            sub_organization__isnull=True,
            organization_name__iexact=F("portfolio__organization_name"),
        )
        requests = DomainRequest.objects.filter(id__in=[request.id for request in requests]).exclude(
            portfolio__isnull=True,
            organization_name__isnull=True,
            sub_organization__isnull=True,
            organization_name__iexact=F("portfolio__organization_name"),
        )
        domains_dict = {domain.organization_name: domain for domain in domains}
        requests_dict = {request.organization_name: request for request in requests}
        logger.info(f"domains_dict: {domains_dict}")
        logger.info(f"requests_dict: {domains_dict}")

        for suborg in suborganizations:
            domain = domains_dict.get(suborg.name, None)
            request = requests_dict.get(suborg.name, None)
            logger.info(f"suborg {suborg}: domain: {domain} , request: {request}")

            # PRIORITY:
            # 1. Domain info
            # 2. Domain request requested suborg fields
            # 3. Domain request normal fields
            city = None
            if domain and domain.city:
                city = normalize_string(domain.city, lowercase=False)
            elif request and request.suborganization_city:
                city = normalize_string(request.suborganization_city, lowercase=False)
            elif request and request.city:
                city = normalize_string(request.city, lowercase=False)

            state_territory = None
            if domain and domain.state_territory:
                state_territory = domain.state_territory
            elif request and request.suborganization_state_territory:
                state_territory = request.suborganization_state_territory
            elif request and request.state_territory:
                state_territory = request.state_territory

            if city:
                suborg.city = city

            if suborg:
                suborg.state_territory = state_territory
            
            logger.info(f"{suborg}: city: {suborg.city}, state: {suborg.state_territory}")

        return Suborganization.objects.bulk_update(suborganizations, ["city", "state_territory"])
