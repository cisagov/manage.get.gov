"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User
from registrar.models.domain import Domain
from registrar.models.domain_invitation import DomainInvitation
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.generic_helper import normalize_string
from django.db.models import F, Q

from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates a federal portfolio given a FederalAgency name"

    def __init__(self, *args, **kwargs):
        """Defines fields to track what portfolios were updated, skipped, or just outright failed."""
        super().__init__(*args, **kwargs)
        self.updated_portfolios = set()
        self.skipped_portfolios = set()
        self.failed_portfolios = set()
        self.added_managers = set()
        self.added_invitations = set()
        self.failed_managers = set()
        self.failed_invitations = set()

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

        Optional:
            --add_managers: Add all domain managers of the portfolio's domains to the organization.
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
        parser.add_argument(
            "--add_managers",
            action=argparse.BooleanOptionalAction,
            help="Add all domain managers of the portfolio's domains to the organization.",
        )

    def handle(self, **options):
        agency_name = options.get("agency_name")
        branch = options.get("branch")
        parse_requests = options.get("parse_requests")
        parse_domains = options.get("parse_domains")
        both = options.get("both")
        add_managers = options.get("add_managers")
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
                # if the portfolio is already created, we don't want to create it again
                portfolio = Portfolio.objects.filter(organization_name=federal_agency.agency)
                if portfolio.exists():
                    portfolio = portfolio.first()
                    message = f"Portfolio '{federal_agency.agency}' already exists. Skipping create."
                    TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
                else:
                    portfolio = self.handle_populate_portfolio(federal_agency, parse_domains, parse_requests, both)
                    portfolios.append(portfolio)
                logger.debug(f"add_managers: {add_managers}")
                if add_managers:
                    logger.debug("Adding managers to portfolio")
                    self.add_managers_to_portfolio(portfolio)
            except Exception as exec:
                self.failed_portfolios.add(federal_agency)
                logger.error(exec)
                message = f"Failed to create portfolio '{federal_agency.agency}'"
                TerminalHelper.colorful_logger(logger.info, TerminalColors.FAIL, message)

        # POST PROCESS STEP: Add additional suborg info where applicable.
        updated_suborg_count = self.post_process_all_suborganization_fields(agencies)
        message = f"Added city and state_territory information to {updated_suborg_count} suborgs."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

        TerminalHelper.log_script_run_summary(
            self.updated_portfolios,
            self.failed_portfolios,
            self.skipped_portfolios,
            debug=False,
            skipped_header="----- SOME PORTFOLIOS WERENT CREATED -----",
            display_as_str=True,
        )

        if add_managers:
            TerminalHelper.log_script_run_summary(
                self.added_managers,
                self.failed_managers,
                [],  # can't skip managers, can only add or fail
                log_header="----- MANAGERS ADDED -----",
                debug=False,
                display_as_str=True,
            )

            TerminalHelper.log_script_run_summary(
                self.added_invitations,
                self.failed_invitations,
                [],  # can't skip invitations, can only add or fail
                log_header="----- INVITATIONS ADDED -----",
                debug=False,
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

    def add_managers_to_portfolio(self, portfolio: Portfolio):
        """
        Add all domain managers of the portfolio's domains to the organization.
        This includes adding them to the correct group and creating portfolio invitations.
        """
        logger.info(f"Adding managers for portfolio {portfolio}")
        
        # Fetch all domains associated with the portfolio
        domains = Domain.objects.filter(domain_info__portfolio=portfolio)
        logger.debug(f"domains: {domains}")
        domain_managers = set()

        # Fetch all users with manager roles for the domains
        managers = UserDomainRole.objects.filter(
            domain__in=domains,
            role=UserDomainRole.Roles.MANAGER
        ).values_list('user', flat=True)
        domain_managers.update(managers)

        invited_managers = set()

        # Get the emails of invited managers
        for domain in domains:
            domain_invitations = DomainInvitation.objects.filter(domain=domain, status=DomainInvitation.DomainInvitationStatus.INVITED).values_list('email', flat=True)
            invited_managers.update(domain_invitations)

        logger.debug(f"invited_managers: {invited_managers}")
        for manager in domain_managers:
            try:
                # manager is a user id
                user = User.objects.get(id=manager)
                _, created = UserPortfolioPermission.objects.get_or_create(
                    portfolio=portfolio,
                    user=user,
                    defaults={"roles": [UserPortfolioRoleChoices.ORGANIZATION_MEMBER]},
                )
                self.added_managers.add(user)
                if created:
                    logger.info(f"Added manager '{user}' to portfolio '{portfolio}'")
                else:
                    logger.info(f"Manager '{user}' already exists in portfolio '{portfolio}'")
            except User.DoesNotExist:
                self.failed_managers.add(user)
                logger.debug(f"User '{user}' does not exist")
        
        for manager in invited_managers:
            self.create_portfolio_invitation(portfolio, manager)

    def create_portfolio_invitation(self, portfolio: Portfolio, email: str):
        """
        Create a portfolio invitation for the given user.
        If the user already has a portfolio invitation, retreive their invitation and create a portfolio permission.
        """
        try:
            logger.debug(f"Creating portfolio invitation for user '{email}'")
            user = User.objects.get(email=email)
            logger.debug(f"user: {user}")
            _, created = PortfolioInvitation.objects.get_or_create(
                portfolio=portfolio,
                user=user,
                defaults={"status": PortfolioInvitation.PortfolioInvitationStatus.INVITED},
            )
            if created:
                logger.info(f"Created portfolio invitation for '{user}' to portfolio '{portfolio}'")
            else:
                logger.info(f"Retrieved existing portfolio invitation for '{user}' to portfolio '{portfolio}'")
            
            # Assign portfolio permissions
            _, created = UserPortfolioPermission.objects.get_or_create(
                portfolio=portfolio,
                user=user,
                defaults={"role": UserPortfolioPermission.RoleChoices.MANAGER},
            )
            if created:
                logger.info(f"Created portfolio permission for '{user}' to portfolio '{portfolio}'")
            else:
                logger.info(f"Retrieved existing portfolio permission for '{user}' to portfolio '{portfolio}'")
            
            self.added_invitations.add(user)
        except User.DoesNotExist:
            PortfolioInvitation.objects.get_or_create(
                portfolio=portfolio,
                email=email,
                defaults={"status": PortfolioInvitation.PortfolioInvitationStatus.INVITED},
            )
            self.added_invitations.add(email)
            logger.info(f"Created portfolio invitation for '{email}' to portfolio '{portfolio}'")
        except Exception as exc:
            self.failed_invitations.add(email)
            logger.error(exc, exc_info=True)
            logger.error(f"Failed to create portfolio invitation for '{email}' to portfolio '{portfolio}'")

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
        message = f"agencies: {agencies}"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

        domain_requests_to_update = DomainRequest.objects.filter(
            federal_agency__in=agencies,
            federal_agency__agency__isnull=False,
            status=DomainRequest.DomainRequestStatus.STARTED,
            organization_name__isnull=False,
        )
        message = (f"domain_requests_to_update: {domain_requests_to_update}") 
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
        portfolio_set = {normalize_string(portfolio.organization_name) for portfolio in portfolios if portfolio}
        message = f"portfolio_set: {portfolio_set}"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

        # Update the request, assuming the given agency name matches the portfolio name
        updated_requests = []
        for req in domain_requests_to_update:
            agency_name = normalize_string(req.federal_agency.agency)
            if agency_name in portfolio_set:
                req.federal_agency = None
                updated_requests.append(req)
            
        message = f"updated_requests: {updated_requests}"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

        # Execute the update and Log the results
        if TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=False,
            prompt_message=(
                f"{len(domain_requests_to_update)} domain requests will be updated. "
                f"These records will be changed: {[str(req) for req in updated_requests]}"
            ),
            prompt_title="Do you wish to commit this update to the database?",
        ):
            message = f"prompted for execution"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
            DomainRequest.objects.bulk_update(updated_requests, ["federal_agency"])
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKBLUE, "Action completed successfully.")

    def handle_populate_portfolio(self, federal_agency, parse_domains, parse_requests, both):
        """Attempts to create a portfolio. If successful, this function will
        also create new suborganizations"""
        portfolio, _ = self.create_portfolio(federal_agency)
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

    def post_process_all_suborganization_fields(self, agencies):
        """Batch updates suborganization locations from domain and request data.

        Args:
            agencies: List of FederalAgency objects to process

        Returns:
            int: Number of suborganizations updated

        Priority for location data:
        1. Domain information
        2. Domain request suborganization fields
        3. Domain request standard fields
        """
        # Common filter between domaininformation / domain request.
        # Filter by only the agencies we've updated thus far.
        # Then, only process records without null portfolio, org name, or suborg name.
        base_filter = Q(
            federal_agency__in=agencies,
            portfolio__isnull=False,
            organization_name__isnull=False,
            sub_organization__isnull=False,
        ) & ~Q(organization_name__iexact=F("portfolio__organization_name"))

        # First: Remove null city / state_territory values on domain info / domain requests.
        # We want to add city data if there is data to add to begin with!
        domains = DomainInformation.objects.filter(
            base_filter,
            Q(city__isnull=False, state_territory__isnull=False),
        )
        requests = DomainRequest.objects.filter(
            base_filter,
            (
                Q(city__isnull=False, state_territory__isnull=False)
                | Q(suborganization_city__isnull=False, suborganization_state_territory__isnull=False)
            ),
        )

        # Second: Group domains and requests by normalized organization name.
        # This means that later down the line we have to account for "duplicate" org names.
        domains_dict = {}
        requests_dict = {}
        for domain in domains:
            normalized_name = normalize_string(domain.organization_name)
            domains_dict.setdefault(normalized_name, []).append(domain)

        for request in requests:
            normalized_name = normalize_string(request.organization_name)
            requests_dict.setdefault(normalized_name, []).append(request)

        # Third: Get suborganizations to update
        suborgs_to_edit = Suborganization.objects.filter(
            Q(id__in=domains.values_list("sub_organization", flat=True))
            | Q(id__in=requests.values_list("sub_organization", flat=True))
        )

        # Fourth: Process each suborg to add city / state territory info
        for suborg in suborgs_to_edit:
            self.post_process_suborganization_fields(suborg, domains_dict, requests_dict)

        # Fifth: Perform a bulk update
        return Suborganization.objects.bulk_update(suborgs_to_edit, ["city", "state_territory"])

    def post_process_suborganization_fields(self, suborg, domains_dict, requests_dict):
        """Updates a single suborganization's location data if valid.

        Args:
            suborg: Suborganization to update
            domains_dict: Dict of domain info records grouped by org name
            requests_dict: Dict of domain requests grouped by org name

        Priority matches parent method. Updates are skipped if location data conflicts
        between multiple records of the same type.
        """
        normalized_suborg_name = normalize_string(suborg.name)
        domains = domains_dict.get(normalized_suborg_name, [])
        requests = requests_dict.get(normalized_suborg_name, [])

        # Try to get matching domain info
        domain = None
        if domains:
            reference = domains[0]
            use_location_for_domain = all(
                d.city == reference.city and d.state_territory == reference.state_territory for d in domains
            )
            if use_location_for_domain:
                domain = reference

        # Try to get matching request info
        # Uses consensus: if all city / state_territory info matches, then we can assume the data is "good".
        # If not, take the safe route and just skip updating this particular record.
        request = None
        use_suborg_location_for_request = True
        use_location_for_request = True
        if requests:
            reference = requests[0]
            use_suborg_location_for_request = all(
                r.suborganization_city
                and r.suborganization_state_territory
                and r.suborganization_city == reference.suborganization_city
                and r.suborganization_state_territory == reference.suborganization_state_territory
                for r in requests
            )
            use_location_for_request = all(
                r.city
                and r.state_territory
                and r.city == reference.city
                and r.state_territory == reference.state_territory
                for r in requests
            )
            if use_suborg_location_for_request or use_location_for_request:
                request = reference

        if not domain and not request:
            message = f"Skipping adding city / state_territory information to suborg: {suborg}. Bad data."
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, message)
            return

        # PRIORITY:
        # 1. Domain info
        # 2. Domain request requested suborg fields
        # 3. Domain request normal fields
        if domain:
            suborg.city = normalize_string(domain.city, lowercase=False)
            suborg.state_territory = domain.state_territory
        elif request and use_suborg_location_for_request:
            suborg.city = normalize_string(request.suborganization_city, lowercase=False)
            suborg.state_territory = request.suborganization_state_territory
        elif request and use_location_for_request:
            suborg.city = normalize_string(request.city, lowercase=False)
            suborg.state_territory = request.state_territory

        message = (
            f"Added city/state_territory to suborg: {suborg}. "
            f"city - {suborg.city}, state - {suborg.state_territory}"
        )
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
