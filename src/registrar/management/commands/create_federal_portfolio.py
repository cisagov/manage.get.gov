"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper, ScriptChangeTracker
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

    class ChangeTracker:
        def __init__(self):
            self.add = []
            self.update = []
            self.skip = []
            self.fail = []

    def __init__(self, *args, **kwargs):
        """Defines fields to track what portfolios were updated, skipped, or just outright failed."""
        super().__init__(*args, **kwargs)
        self.updated_portfolios = set()
        self.skipped_portfolios = set()
        self.failed_portfolios = set()
        self.added_managers = set()
        self.added_invitations = set()
        self.skipped_invitations = set()
        self.failed_managers = set()
        self.portfolio_changes = self.ChangeTracker()
        self.suborganization_changes = self.ChangeTracker()
        self.domain_info_changes = self.ChangeTracker()
        self.domain_request_changes = self.ChangeTracker()
        self.user_domain_role_changes = self.ChangeTracker()
        self.portfolio_invitation_changes = self.ChangeTracker()

    def add_arguments(self, parser):
        """Add command line arguments to create federal portfolios.

        Required (mutually exclusive) arguments:
            --agency_name: Name of a specific FederalAgency to create a portfolio for
            --branch: Federal branch to process ("executive", "legislative", or "judicial").
                    Creates portfolios for all FederalAgencies in that branch.

        Required (at least one):
            --parse_requests: Add the created portfolio(s) to related DomainRequest records
            --parse_domains: Add the created portfolio(s) to related DomainInformation records

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
            "--parse_managers",
            action=argparse.BooleanOptionalAction,
            help="Add all domain managers of the portfolio's domains to the organization.",
        )
        parser.add_argument(
            "--skip_existing_portfolios",
            action=argparse.BooleanOptionalAction,
            help="Only add suborganizations to newly created portfolios, skip existing ones.",
        )

    def handle(self, **options):  # noqa: C901
        agency_name = options.get("agency_name")
        branch = options.get("branch")
        parse_requests = options.get("parse_requests")
        parse_domains = options.get("parse_domains")
        parse_managers = options.get("parse_managers")
        skip_existing_portfolios = options.get("skip_existing_portfolios")

        # Parse script params
        if not (parse_requests or parse_domains or parse_managers):
            raise CommandError("You must specify at least one of --parse_requests, --parse_domains, or --parse_managers.")

        # Get agencies
        federal_agency_filter = {"agency__iexact": agency_name} if agency_name else {"federal_type": branch}
        agencies = FederalAgency.objects.filter(**federal_agency_filter)
        if not agencies.exists():
            if agency_name:
                raise CommandError(
                    f"Cannot find the federal agency '{agency_name}' in our database. "
                    "The value you enter for `agency_name` must be "
                    "prepopulated in the FederalAgency table before proceeding."
                )
            else:
                raise CommandError(f"Cannot find '{branch}' federal agencies in our database.")

        # Parse portfolios
        portfolios = []
        for federal_agency in agencies:
            message = f"Processing federal agency '{federal_agency.agency}'..."
            logger.info(f"{TerminalColors.MAGENTA}{message}{TerminalColors.ENDC}")
            portfolio, created = self.get_or_create_portfolio(federal_agency)
            if skip_existing_portfolios and not created:
                message = (
                    "Skipping modifications to suborgs, domain requests, and "
                    "domains due to the --skip_existing_portfolios flag. Portfolio already exists."
                )
                logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
            else:
                # if parse_suborganizations
                self.create_suborganizations(portfolio, federal_agency)
                if parse_domains:
                    self.handle_portfolio_domains(portfolio, federal_agency)

                if parse_requests:
                    self.handle_portfolio_requests(portfolio, federal_agency)

                portfolios.append(portfolio)
                if parse_managers:
                    self.handle_portfolio_managers(portfolio)

        # POST PROCESS STEP: Add additional suborg info where applicable.
        updated_suborg_count = self.post_process_all_suborganization_fields(agencies)
        message = f"Added city and state_territory information to {updated_suborg_count} suborgs."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
        TerminalHelper.log_script_run_summary(
            **vars(self.portfolio_changes),
            debug=False,
            log_header="============= FINISHED HANDLE PORTFOLIO STEP ===============",
            skipped_header="----- SOME PORTFOLIOS WERENT CREATED (BUT OTHER RECORDS ARE STILL PROCESSED) -----",
            display_as_str=True,
        )

        if parse_managers:
            TerminalHelper.log_script_run_summary(
                **vars(self.user_domain_role_changes),
                log_header="----- MANAGERS ADDED -----",
                debug=False,
                display_as_str=True,
            )

            TerminalHelper.log_script_run_summary(
                **vars(self.portfolio_invitation_changes),
                log_header="----- INVITATIONS ADDED -----",
                debug=False,
                skipped_header="----- INVITATIONS SKIPPED (ALREADY EXISTED) -----",
                display_as_str=True,
            )

        # POST PROCESSING STEP: Remove the federal agency if it matches the portfolio name.
        # We only do this for started domain requests.
        if parse_requests:
            prompt_message = (
                "This action will update domain requests even if they aren't on a portfolio."
                "\nNOTE: This will modify domain requests, even if no portfolios were created."
                "\nIn the event no portfolios *are* created, then this step will target "
                "the existing portfolios with your given params."
                "\nThis step is entirely optional, and is just for extra data cleanup."
            )
            TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=True,
                prompt_message=prompt_message,
                prompt_title=(
                    "POST PROCESS STEP: Do you want to clear federal agency on (related) started domain requests?"
                ),
                verify_message="*** THIS STEP IS OPTIONAL ***",
            )
            self.post_process_started_domain_requests(agencies, portfolios)

    def get_or_create_portfolio(self, federal_agency):
        portfolio_name = normalize_string(federal_agency.agency, lowercase=False)
        portfolio, created = Portfolio.objects.get_or_create(
            organization_name=portfolio_name,
            federal_agency=federal_agency,
            organization_type=DomainRequest.OrganizationChoices.FEDERAL,
            creator=User.get_default_user(),
            notes="Auto-generated record",
            senior_official=federal_agency.so_federal_agency.first(),
        )

        if created:
            self.portfolio_changes.add.append(portfolio)
            logger.info(f"{TerminalColors.OKGREEN}Created portfolio '{portfolio}'.{TerminalColors.ENDC}")
        else:
            self.skipped_portfolios.add(portfolio)
            message = f"Portfolio with organization name '{portfolio}' already exists. Skipping create."
            logger.info(f"{TerminalColors.OKGREEN}{message}{TerminalColors.ENDC}")

        return portfolio, created

    def create_suborganizations(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """Create Suborganizations tied to the given portfolio based on DomainInformation objects"""
        message = f"Creating suborgs for portfolio {portfolio}."
        logger.info(f"{TerminalColors.MAGENTA}{message}{TerminalColors.ENDC}")

        valid_agencies = federal_agency.domaininformation_set.filter(organization_name__isnull=False)
        org_names = set(valid_agencies.values_list("organization_name", flat=True))
        existing_org_names = set(
            Suborganization.objects
            .filter(name__in=org_names)
            .values_list("name", flat=True)
        )
        for name in org_names - existing_org_names:
            if normalize_string(name) == normalize_string(portfolio.organization_name):
                self.suborganization_changes.skip.append(suborg)
                message = (
                    f"Skipping suborganization create on record '{name}'. "
                    "The federal agency name is the same as the portfolio name."
                )
                logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
            else:
                suborg_name = normalize_string(name)
                suborg = Suborganization(name=suborg_name, portfolio=portfolio)
                self.suborganization_changes.add.append(suborg)

        suborg_add_count = len(self.suborganization_changes.add)
        if suborg_add_count > 0:
            Suborganization.objects.bulk_create(self.suborganization_changes.add)
            message = f"Added {suborg_add_count} suborganizations to '{federal_agency}'."
            logger.info(f"{TerminalColors.OKGREEN}{message}{TerminalColors.ENDC}")
        else:
            message = f"No suborganizations added for '{federal_agency}'."
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domains for a federal agency.
        Updates all relevant domain information records.

        Returns a queryset of DomainInformation objects, or None if nothing changed.
        """
        message = f"Adding domains to portfolio {portfolio}."
        logger.info(f"{TerminalColors.MAGENTA}{message}{TerminalColors.ENDC}")

        domain_infos = federal_agency.domaininformation_set.all()
        if not domain_infos.exists():
            message = f"""
            Portfolio '{portfolio}' not added to domains: no valid records found.
            The filter on DomainInformation for the federal_agency '{federal_agency}' returned no results.
            """
            logger.info(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
            return None

        # Get all suborg information and store it in a dict to avoid doing a db call
        suborgs = Suborganization.objects.filter(portfolio=portfolio).in_bulk(field_name="name")
        for domain_info in domain_infos:
            org_name = normalize_string(domain_info.organization_name, lowercase=False)
            domain_info.portfolio = portfolio
            domain_info.sub_organization = suborgs.get(org_name, None)
            self.domain_info_changes.update.append(domain_info)

        DomainInformation.objects.bulk_update(domain_infos, ["portfolio", "sub_organization"])
        message = f"Added portfolio '{portfolio}' to {len(domain_infos)} domains."
        logger.info(f"{TerminalColors.OKGREEN}{message}{TerminalColors.ENDC}")

    def handle_portfolio_requests(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domain requests for a federal agency.
        Updates all relevant domain request records.
        """
        message = f"Adding domain requests to portfolio {portfolio}."
        logger.info(f"{TerminalColors.MAGENTA}{message}{TerminalColors.ENDC}")

        invalid_states = [
            DomainRequest.DomainRequestStatus.STARTED,
            DomainRequest.DomainRequestStatus.INELIGIBLE,
            DomainRequest.DomainRequestStatus.REJECTED,
        ]
        domain_requests = DomainRequest.objects.filter(federal_agency=federal_agency).exclude(status__in=invalid_states)
        if not domain_requests.exists():
            message = f"""
            Portfolio '{portfolio}' not added to domain requests: nothing to add found.
            Excluded statuses: STARTED, INELIGIBLE, REJECTED.
            """
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return None

        # Get all suborg information and store it in a dict to avoid doing a db call
        suborgs = Suborganization.objects.filter(portfolio=portfolio).in_bulk(field_name="name")
        for domain_request in domain_requests:
            org_name = normalize_string(domain_request.organization_name, lowercase=False)
            domain_request.portfolio = portfolio
            domain_request.sub_organization = suborgs.get(org_name, None)
            if domain_request.sub_organization is None:
                domain_request.requested_suborganization = normalize_string(
                    domain_request.organization_name, lowercase=False
                )
                domain_request.suborganization_city = normalize_string(domain_request.city, lowercase=False)
                domain_request.suborganization_state_territory = domain_request.state_territory
            self.domain_request_changes.add.append(portfolio)

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
        logger.info(f"{TerminalColors.OKGREEN}{message}{TerminalColors.ENDC}")

    # TODO - this doesn't send an email out, should it?
    def handle_portfolio_managers(self, portfolio: Portfolio):
        """
        Add all domain managers of the portfolio's domains to the organization.
        This includes adding them to the correct group and creating portfolio invitations.
        """
        message = f"Adding managers to portfolio {portfolio}."
        logger.info(f"{TerminalColors.MAGENTA}{message}{TerminalColors.ENDC}")

        domains = portfolio.information_portfolio.all().values_list("domain", flat=True)

        # Fetch all users with manager roles for the domains
        user_domain_roles = UserDomainRole.objects.select_related("user").filter(
            domain__in=domains, role=UserDomainRole.Roles.MANAGER
        )
        existing_permissions = UserPortfolioPermission.objects.filter(
            user__in=user_domain_roles.values_list("user")
        ).in_bulk(field_name="user")
        for user_domain_role in user_domain_roles:
            user = user_domain_role.user
            if user not in existing_permissions:
                permission = UserPortfolioPermission(
                    portfolio=portfolio,
                    user=user,
                    roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
                )
                self.user_domain_role_changes.add.append(permission)
                logger.info(f"Added manager '{permission.user}' to portfolio '{portfolio}'.")
            else:
                existing_permission = existing_permissions.get(user)
                self.user_domain_role_changes.skip.append(existing_permission)
                logger.info(f"Manager '{permission.user}' already exists in portfolio '{portfolio}'.")

        # Bulk create user portfolio permissions
        UserPortfolioPermission.objects.bulk_create(self.user_domain_role_changes.add)

        # TODO - needs normalize step
        # Get the emails of invited managers
        domain_invitations = DomainInvitation.objects.filter(
            domain__in=domains, status=DomainInvitation.DomainInvitationStatus.INVITED
        )
        existing_invitations = PortfolioInvitation.objects.filter(
            email__in=domain_invitations.values_list("email")
        ).in_bulk(field_name="user")
        for domain_invitation in domain_invitations:
            email = domain_invitation.email
            if email not in existing_invitations:
                invitation = PortfolioInvitation(
                    portfolio=portfolio,
                    email=email,
                    status = PortfolioInvitation.PortfolioInvitationStatus.INVITED,
                    roles = [UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
                )
                self.portfolio_invitation_changes.add.append(invitation)
                logger.info(f"Added invitation '{email}' to portfolio '{portfolio}'.")
            else:
                existing_invitation = existing_invitations.get(email)
                self.portfolio_invitation_changes.skip.append(existing_invitation)
                logger.info(f"Invitation '{email}' already exists in portfolio '{portfolio}'.")

        # Bulk create portfolio invitations
        PortfolioInvitation.objects.bulk_create(self.user_domain_role_changes.add)

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

        if domain_requests_to_update.count() == 0:
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, "No domain requests to update.")
            return

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
            prompt_title="Do you wish to commit this update to the database?",
        ):
            DomainRequest.objects.bulk_update(updated_requests, ["federal_agency"])
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKBLUE, "Action completed successfully.")

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
