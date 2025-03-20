"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import ScriptDataHelper, TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User
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
        def __init__(self, model_class):
            self.model_class = model_class
            self.create = []
            self.update = []
            self.skip = []
            self.fail = []

        def print_script_run_summary(self, no_changes_message, **kwargs):
            """Helper function that runs TerminalHelper.log_script_run_summary on this object."""
            if self.has_changes():
                TerminalHelper.log_script_run_summary(self.create, self.update, self.skip, self.fail, **kwargs)
            else:
                logger.info(f"{TerminalColors.BOLD}{no_changes_message}{TerminalColors.ENDC}")

        def has_changes(self) -> bool:
            num_changes = [len(self.create), len(self.update), len(self.skip), len(self.fail)]
            return any([num_change > 0 for num_change in num_changes])

        def bulk_create(self):
            try:
                ScriptDataHelper.bulk_create_fields(self.model_class, self.create, quiet=True)
            except Exception as err:
                # In this case, just swap the fail and add lists
                self.fail = self.create.copy()
                self.create.clear()
                raise err

        def bulk_update(self, fields_to_update):
            try:
                ScriptDataHelper.bulk_update_fields(self.model_class, self.update, fields_to_update, quiet=True)
            except Exception as err:
                # In this case, just swap the fail and update lists
                self.fail = self.update.copy()
                self.update.clear()
                raise err

    def __init__(self, *args, **kwargs):
        """Defines fields to track what portfolios were updated, skipped, or just outright failed."""
        super().__init__(*args, **kwargs)
        self.portfolio_changes = self.ChangeTracker(model_class=Portfolio)
        self.suborganization_changes = self.ChangeTracker(model_class=Suborganization)
        self.domain_info_changes = self.ChangeTracker(model_class=DomainInformation)
        self.domain_request_changes = self.ChangeTracker(model_class=DomainRequest)
        self.user_portfolio_perm_changes = self.ChangeTracker(model_class=UserPortfolioPermission)
        self.portfolio_invitation_changes = self.ChangeTracker(model_class=PortfolioInvitation)

    def add_arguments(self, parser):
        """Add command line arguments to create federal portfolios.

        Required (mutually exclusive) arguments:
            --agency_name: Name of a specific FederalAgency to create a portfolio for
            --branch: Federal branch to process ("executive", "legislative", or "judicial").
                    Creates portfolios for all FederalAgencies in that branch.

        Required (at least one):
            --parse_requests: Add the created portfolio(s) to related DomainRequest records
            --parse_domains: Add the created portfolio(s) to related DomainInformation records
            --parse_managers: Add all domain managers of the portfolio's domains to the organization.

        Optional:
            --skip_existing_portfolios: Does not perform substeps on a portfolio if it already exists.
            -- clear_federal_agency_on_started_domain_requests: Parses started domain requests
            --debug: Increases log verbosity
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
            help="Only parses newly created portfolios, skippubg existing ones.",
        )
        parser.add_argument(
            "--clear_federal_agency_on_started_domain_requests",
            action=argparse.BooleanOptionalAction,
            help="Clears the federal agency field on started domain requests under the given portfolio",
        )
        parser.add_argument(
            "--debug",
            action=argparse.BooleanOptionalAction,
            help="Shows additional log info.",
        )

    def handle(self, **options):  # noqa: C901
        agency_name = options.get("agency_name")
        branch = options.get("branch")
        parse_requests = options.get("parse_requests")
        parse_domains = options.get("parse_domains")
        parse_managers = options.get("parse_managers")
        skip_existing_portfolios = options.get("skip_existing_portfolios")
        clear_federal_agency_on_started_domain_requests = options.get("clear_federal_agency_on_started_domain_requests")
        debug = options.get("debug")

        # Parse script params
        if not (parse_requests or parse_domains or parse_managers):
            raise CommandError(
                "You must specify at least one of --parse_requests, --parse_domains, or --parse_managers."
            )

        # Get agencies
        federal_agency_filter = {"agency__iexact": agency_name} if agency_name else {"federal_type": branch}
        agencies = FederalAgency.objects.filter(agency__isnull=False, **federal_agency_filter).distinct()
        if not agencies.exists():
            if agency_name:
                raise CommandError(
                    f"Cannot find the federal agency '{agency_name}' in our database. "
                    "The value you enter for `agency_name` must be "
                    "prepopulated in the FederalAgency table before proceeding."
                )
            else:
                raise CommandError(f"Cannot find '{branch}' federal agencies in our database.")

        # NOTE: exceptions to portfolio and suborg are intentionally uncaught.
        # parse domains, requests, and managers all rely on these fields to function.
        # An error here means everything down the line is compromised.
        # The individual parse steps, however, are independent from eachother.

        # == Handle portfolios == #
        # TODO - some kind of duplicate check on agencies and existing portfolios
        existing_portfolios = Portfolio.objects.filter(
            organization_name__in=agencies.values_list("agency", flat=True), organization_name__isnull=False
        )
        existing_portfolios_set = {normalize_string(p.organization_name): p for p in existing_portfolios}
        agencies_set = {normalize_string(agency.agency): agency for agency in agencies}
        for federal_agency in agencies_set.values():
            portfolio_name = normalize_string(federal_agency.agency, lowercase=False)
            portfolio = existing_portfolios_set.get(portfolio_name, None)
            new_portfolio = portfolio is None
            if new_portfolio:
                portfolio = Portfolio(
                    organization_name=portfolio_name,
                    federal_agency=federal_agency,
                    organization_type=DomainRequest.OrganizationChoices.FEDERAL,
                    creator=User.get_default_user(),
                    notes="Auto-generated record",
                    senior_official=federal_agency.so_federal_agency.first(),
                )
                self.portfolio_changes.create.append(portfolio)
                logger.info(f"{TerminalColors.OKGREEN}Created portfolio '{portfolio}'.{TerminalColors.ENDC}")

            if skip_existing_portfolios and not new_portfolio:
                message = f"Portfolio '{portfolio}' already exists. Skipped."
                logger.info(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
                if portfolio:
                    self.portfolio_changes.skip.append(portfolio)

        # Create portfolios
        self.portfolio_changes.bulk_create()

        # After create, get the list of all portfolios to use
        portfolios_to_use = set(self.portfolio_changes.create)
        if not skip_existing_portfolios:
            portfolios_to_use.update(set(existing_portfolios))

        # == Handle suborganizations == #
        for portfolio in portfolios_to_use:
            created_suborgs = []
            org_name = normalize_string(portfolio.organization_name)
            federal_agency = agencies_set.get(org_name)
            if portfolio:
                created_suborgs = self.create_suborganizations(portfolio, federal_agency)
                Suborganization.objects.bulk_create(created_suborgs)
                self.suborganization_changes.create.extend(created_suborgs)

        # == Handle domains, requests, and managers == #
        for portfolio in portfolios_to_use:
            org_name = normalize_string(portfolio.organization_name)
            federal_agency = agencies_set.get(org_name)

            if parse_domains:
                self.handle_portfolio_domains(portfolio, federal_agency)

            if parse_requests:
                self.handle_portfolio_requests(
                    portfolio, federal_agency, clear_federal_agency_on_started_domain_requests, debug
                )

            if parse_managers:
                self.handle_portfolio_managers(portfolio, debug)

        # Update DomainInformation
        try:
            self.domain_info_changes.bulk_update(["portfolio", "sub_organization"])
        except Exception as err:
            logger.error(f"{TerminalColors.FAIL}Could not bulk update domain infos.{TerminalColors.ENDC}")
            logger.error(err, exc_info=True)

        # Update DomainRequest
        try:
            self.domain_request_changes.bulk_update(
                [
                    "portfolio",
                    "sub_organization",
                    "requested_suborganization",
                    "suborganization_city",
                    "suborganization_state_territory",
                    "federal_agency",
                ]
            )
        except Exception as err:
            logger.error(f"{TerminalColors.FAIL}Could not bulk update domain requests.{TerminalColors.ENDC}")
            logger.error(err, exc_info=True)

        # Create UserPortfolioPermission
        try:
            self.user_portfolio_perm_changes.bulk_create()
        except Exception as err:
            logger.error(f"{TerminalColors.FAIL}Could not bulk create user portfolio permissions.{TerminalColors.ENDC}")
            logger.error(err, exc_info=True)

        # Create PortfolioInvitation
        try:
            self.portfolio_invitation_changes.bulk_create()
        except Exception as err:
            logger.error(f"{TerminalColors.FAIL}Could not bulk create portfolio invitations.{TerminalColors.ENDC}")
            logger.error(err, exc_info=True)

        # == PRINT RUN SUMMARY == #
        self.print_final_run_summary(parse_domains, parse_requests, parse_managers, debug)

    def print_final_run_summary(self, parse_domains, parse_requests, parse_managers, debug):
        self.portfolio_changes.print_script_run_summary(
            no_changes_message="\n||============= No portfolios changed. =============||",
            debug=debug,
            log_header="============= PORTFOLIOS =============",
            skipped_header="----- SOME PORTFOLIOS WERENT CREATED (BUT OTHER RECORDS ARE STILL PROCESSED) -----",
            detailed_prompt_title="PORTFOLIOS: Do you wish to see the full list of failed, skipped and updated records?",
            display_as_str=True,
        )
        self.suborganization_changes.print_script_run_summary(
            no_changes_message="\n||============= No suborganizations changed. =============||",
            debug=debug,
            log_header="============= SUBORGANIZATIONS =============",
            skipped_header="----- SUBORGANIZATIONS SKIPPED (SAME NAME AS PORTFOLIO NAME) -----",
            detailed_prompt_title="SUBORGANIZATIONS: Do you wish to see the full list of failed, skipped and updated records?",
            display_as_str=True,
        )

        if parse_domains:
            self.domain_info_changes.print_script_run_summary(
                no_changes_message="||============= No domains changed. =============||",
                debug=debug,
                log_header="============= DOMAINS =============",
                detailed_prompt_title="DOMAINS: Do you wish to see the full list of failed, skipped and updated records?",
                display_as_str=True,
            )

        if parse_requests:
            self.domain_request_changes.print_script_run_summary(
                no_changes_message="||============= No domain requests changed. =============||",
                debug=debug,
                log_header="============= DOMAIN REQUESTS =============",
                detailed_prompt_title="DOMAIN REQUESTS: Do you wish to see the full list of failed, skipped and updated records?",
                display_as_str=True,
            )

        if parse_managers:
            self.user_portfolio_perm_changes.print_script_run_summary(
                no_changes_message="||============= No managers changed. =============||",
                log_header="============= MANAGERS =============",
                skipped_header="----- MANAGERS SKIPPED (ALREADY EXISTED) -----",
                debug=debug,
                detailed_prompt_title="MANAGERS: Do you wish to see the full list of failed, skipped and updated records?",
                display_as_str=True,
            )
            self.portfolio_invitation_changes.print_script_run_summary(
                no_changes_message="||============= No manager invitations changed. =============||",
                log_header="============= MANAGER INVITATIONS =============",
                debug=debug,
                skipped_header="----- INVITATIONS SKIPPED (ALREADY EXISTED) -----",
                detailed_prompt_title="MANAGER INVITATIONS: Do you wish to see the full list of failed, skipped and updated records?",
                display_as_str=True,
            )

    def create_suborganizations(self, portfolio, federal_agency):
        """Create Suborganizations tied to the given portfolio based on DomainInformation objects"""
        base_filter = Q(
            organization_name__isnull=False,
        ) & ~Q(organization_name__iexact=F("portfolio__organization_name"))

        domains = federal_agency.domaininformation_set.filter(base_filter)
        requests = federal_agency.domainrequest_set.filter(base_filter)
        existing_orgs = Suborganization.objects.all()

        # Normalize all suborg names so we don't add duplicate data unintentionally.
        # Get all suborg names that we COULD add
        org_names_normalized = {}
        for domain in domains:
            org_name = normalize_string(domain.organization_name)
            if org_name not in org_names_normalized:
                org_names_normalized[org_name] = domain.organization_name

        # Get all suborg names that presently exist
        existing_org_names_normalized = {}
        for org in existing_orgs:
            org_name = normalize_string(org.name)
            if org_name not in existing_org_names_normalized:
                existing_org_names_normalized[org_name] = org.name

        # Subtract existing names from ones we COULD add.
        # We don't want to add existing names.
        new_org_names = {}
        for norm_name, name in org_names_normalized.items():
            if norm_name not in existing_org_names_normalized:
                new_org_names[norm_name] = name

        # Add new suborgs assuming they aren't duplicates and don't already exist in the db.
        created_suborgs = []
        for norm_name, name in new_org_names.items():
            norm_portfolio_name = normalize_string(portfolio.organization_name)
            if norm_name != norm_portfolio_name:
                suborg = Suborganization(name=name, portfolio=portfolio)
                created_suborgs.append(suborg)

        # Add location information to suborgs.
        # This can vary per domain and request, so this is a seperate step.
        # First: Filter domains and requests by those that have data
        valid_domains = domains.filter(
            city__isnull=False,
            state_territory__isnull=False,
            portfolio__isnull=False,
            sub_organization__isnull=False,
        )
        valid_requests = requests.filter(
            (
                Q(city__isnull=False, state_territory__isnull=False)
                | Q(suborganization_city__isnull=False, suborganization_state_territory__isnull=False)
            ),
            portfolio__isnull=False,
            sub_organization__isnull=False,
        )

        # Second: Group domains and requests by normalized organization name.
        # This means that later down the line we can account for "duplicate" org names.
        domains_dict = {}
        requests_dict = {}
        for domain in valid_domains:
            print(f"what is the org name? {domain.organization_name}")
            normalized_name = normalize_string(domain.organization_name)
            domains_dict.setdefault(normalized_name, []).append(domain)

        for request in valid_requests:
            print(f"what is the org name for requests? {request.organization_name}")
            normalized_name = normalize_string(request.organization_name)
            requests_dict.setdefault(normalized_name, []).append(request)

        # Fourth: Process each suborg to add city / state territory info
        for suborg in created_suborgs:
            self.set_suborganization_location(suborg, domains_dict, requests_dict)
        
        return created_suborgs

    def set_suborganization_location(self, suborg, domains_dict, requests_dict):
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
        print(f"domains: {domains}")
        print(f"requests: {requests}")

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
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
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

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domains for a federal agency.
        Updates all relevant domain information records.

        Returns a queryset of DomainInformation objects, or None if nothing changed.
        """
        domain_infos = federal_agency.domaininformation_set.all()
        if not domain_infos.exists():
            return None

        # Get all suborg information and store it in a dict to avoid doing a db call
        suborgs = Suborganization.objects.filter(portfolio=portfolio).in_bulk(field_name="name")
        for domain_info in domain_infos:
            org_name = normalize_string(domain_info.organization_name, lowercase=False)
            domain_info.portfolio = portfolio
            domain_info.sub_organization = suborgs.get(org_name, None)
            self.domain_info_changes.update.append(domain_info)

    def handle_portfolio_requests(
        self,
        portfolio: Portfolio,
        federal_agency: FederalAgency,
        clear_federal_agency_on_started_domain_requests: bool,
        debug: bool,
    ):
        """
        Associate portfolio with domain requests for a federal agency.
        Updates all relevant domain request records.
        """
        invalid_states = [
            DomainRequest.DomainRequestStatus.STARTED,
            DomainRequest.DomainRequestStatus.INELIGIBLE,
            DomainRequest.DomainRequestStatus.REJECTED,
        ]
        domain_requests = DomainRequest.objects.filter(federal_agency=federal_agency).exclude(status__in=invalid_states)
        if not domain_requests.exists():
            if debug:
                message = (
                    f"Portfolio '{portfolio}' not added to domain requests: nothing to add found."
                    "Excluded statuses: STARTED, INELIGIBLE, REJECTED."
                )
                logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
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
            self.domain_request_changes.update.append(domain_request)

        # For each STARTED request, clear the federal agency under these conditions:
        # 1. A portfolio *already exists* with the same name as the federal agency.
        # 2. Said portfolio (or portfolios) are only the ones specified at the start of the script.
        # 3. The domain request is in status "started".
        # Note: Both names are normalized so excess spaces are stripped and the string is lowercased.
        if clear_federal_agency_on_started_domain_requests:
            started_domain_requests = federal_agency.domainrequest_set.filter(
                status=DomainRequest.DomainRequestStatus.STARTED,
                organization_name__isnull=False,
            )

            portfolio_name = normalize_string(portfolio.organization_name)

            # Update the request, assuming the given agency name matches the portfolio name
            for domain_request in started_domain_requests:
                agency_name = normalize_string(domain_request.federal_agency.agency)
                if agency_name == portfolio_name:
                    domain_request.federal_agency = None
                    self.domain_request_changes.update.append(domain_request)

    def handle_portfolio_managers(self, portfolio: Portfolio, debug):
        """
        Add all domain managers of the portfolio's domains to the organization.
        This includes adding them to the correct group and creating portfolio invitations.
        """
        domains = portfolio.information_portfolio.all().values_list("domain", flat=True)

        # Fetch all users with manager roles for the domains
        user_domain_roles = UserDomainRole.objects.select_related("user").filter(
            domain__in=domains, role=UserDomainRole.Roles.MANAGER
        )
        existing_permissions = UserPortfolioPermission.objects.filter(
            user__in=user_domain_roles.values_list("user"), portfolio=portfolio
        )
        existing_permissions_dict = {permission.user: permission for permission in existing_permissions}
        for user_domain_role in user_domain_roles:
            user = user_domain_role.user
            if user not in existing_permissions_dict:
                permission = UserPortfolioPermission(
                    portfolio=portfolio,
                    user=user,
                    roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
                )
                self.user_portfolio_perm_changes.create.append(permission)
                if debug:
                    logger.info(f"Added manager '{permission.user}' to portfolio '{portfolio}'.")
            else:
                existing_permission = existing_permissions_dict.get(user)
                self.user_portfolio_perm_changes.skip.append(existing_permission)
                if debug:
                    logger.info(f"Manager '{user}' already exists on portfolio '{portfolio}'.")

        # Get the emails of invited managers
        domain_invitations = DomainInvitation.objects.filter(
            domain__in=domains, status=DomainInvitation.DomainInvitationStatus.INVITED
        )
        existing_invitations = PortfolioInvitation.objects.filter(
            email__in=domain_invitations.values_list("email"), portfolio=portfolio
        )
        existing_invitation_dict = {normalize_string(invite.email): invite for invite in existing_invitations}
        for domain_invitation in domain_invitations:
            email = normalize_string(domain_invitation.email)
            if email not in existing_invitation_dict:
                invitation = PortfolioInvitation(
                    portfolio=portfolio,
                    email=email,
                    status=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
                    roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
                )
                self.portfolio_invitation_changes.create.append(invitation)
                if debug:
                    logger.info(f"Added invitation '{email}' to portfolio '{portfolio}'.")
            else:
                existing_invitation = existing_invitations.get(email)
                self.portfolio_invitation_changes.skip.append(existing_invitation)
                if debug:
                    logger.info(f"Invitation '{email}' already exists in portfolio '{portfolio}'.")
