"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import ScriptDataHelper, TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User
from registrar.models.domain import Domain
from registrar.models.domain_invitation import DomainInvitation
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.generic_helper import count_capitals, normalize_string
from django.db.models import F, Q

from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices, UserPortfolioPermissionChoices

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
            changes = [self.create, self.update, self.skip, self.fail]
            return any([change for change in changes if change])

        def bulk_create(self):
            try:
                res = ScriptDataHelper.bulk_create_fields(
                    self.model_class, self.create, return_created=True, quiet=True
                )
                self.create = res
                return res
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
            help="Only parses newly created portfolios, skipping existing ones.",
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

        # Store all portfolios and agencies in a dict to avoid extra db calls
        existing_portfolios = Portfolio.objects.filter(
            organization_name__in=agencies.values_list("agency", flat=True), organization_name__isnull=False
        )
        existing_portfolios_dict = {normalize_string(p.organization_name): p for p in existing_portfolios}
        agencies_dict = {normalize_string(agency.agency): agency for agency in agencies}

        # NOTE: exceptions to portfolio and suborg are intentionally uncaught.
        # parse domains, requests, and managers all rely on these fields to function.
        # An error here means everything down the line is compromised.
        # The individual parse steps, however, are independent from eachother.

        # == Handle portfolios == #
        # Loop through every agency we want to add and create a portfolio if the record is new.
        for federal_agency in agencies_dict.values():
            norm_agency_name = normalize_string(federal_agency.agency)
            portfolio = existing_portfolios_dict.get(norm_agency_name, None)
            if portfolio is None:
                portfolio = Portfolio(
                    organization_name=federal_agency.agency,
                    federal_agency=federal_agency,
                    organization_type=DomainRequest.OrganizationChoices.FEDERAL,
                    requester=User.get_default_user(),
                    notes="Auto-generated record",
                    senior_official=federal_agency.so_federal_agency.first(),
                )
                self.portfolio_changes.create.append(portfolio)
                logger.info(f"{TerminalColors.OKGREEN}Created portfolio '{portfolio}'.{TerminalColors.ENDC}")
            elif skip_existing_portfolios:
                message = f"Portfolio '{portfolio}' already exists. Skipped."
                logger.info(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
                self.portfolio_changes.skip.append(portfolio)

        # Create portfolios
        self.portfolio_changes.bulk_create()

        # After create, get the list of all portfolios to use
        portfolios_to_use = set(self.portfolio_changes.create)
        if not skip_existing_portfolios:
            portfolios_to_use.update(set(existing_portfolios))

        portfolios_to_use_dict = {normalize_string(p.organization_name): p for p in portfolios_to_use}

        # == Handle suborganizations == #
        created_suborgs = self.create_suborganizations(portfolios_to_use_dict, agencies_dict)
        if created_suborgs:
            self.suborganization_changes.create.extend(created_suborgs.values())
            self.suborganization_changes.bulk_create()

        # == Handle domains and requests == #
        for portfolio_org_name, portfolio in portfolios_to_use_dict.items():
            federal_agency = agencies_dict.get(portfolio_org_name)
            suborgs = {}
            for suborg in portfolio.portfolio_suborganizations.all():
                suborgs[suborg.name] = suborg

            if parse_domains:
                updated_domains = self.update_domains(portfolio, federal_agency, suborgs, debug)
                self.domain_info_changes.update.extend(updated_domains)

            if parse_requests:
                updated_domain_requests = self.update_requests(portfolio, federal_agency, suborgs, debug)
                self.domain_request_changes.update.extend(updated_domain_requests)

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

        # == Handle managers (no bulk_create) == #
        if parse_managers:
            domain_infos = DomainInformation.objects.filter(portfolio__in=portfolios_to_use)
            domains = Domain.objects.filter(domain_info__in=domain_infos)

            # Create UserPortfolioPermission
            self.create_user_portfolio_permissions(domains)

            # Create PortfolioInvitation
            self.create_portfolio_invitations(domains)

        # == PRINT RUN SUMMARY == #
        self.print_final_run_summary(parse_domains, parse_requests, parse_managers, debug)

    def print_final_run_summary(self, parse_domains, parse_requests, parse_managers, debug):
        self.portfolio_changes.print_script_run_summary(
            no_changes_message="||============= No portfolios changed. =============||",
            log_header="============= PORTFOLIOS =============",
            skipped_header="----- SOME PORTFOLIOS WERENT CREATED (BUT OTHER RECORDS ARE STILL PROCESSED) -----",
            detailed_prompt_title=(
                "PORTFOLIOS: Do you wish to see the full list of failed, skipped and updated records?"
            ),
            display_as_str=True,
            debug=debug,
        )
        self.suborganization_changes.print_script_run_summary(
            no_changes_message="||============= No suborganizations changed. =============||",
            log_header="============= SUBORGANIZATIONS =============",
            skipped_header="----- SUBORGANIZATIONS SKIPPED (SAME NAME AS PORTFOLIO NAME) -----",
            detailed_prompt_title=(
                "SUBORGANIZATIONS: Do you wish to see the full list of failed, skipped and updated records?"
            ),
            display_as_str=True,
            debug=debug,
        )

        if parse_domains:
            self.domain_info_changes.print_script_run_summary(
                no_changes_message="||============= No domains changed. =============||",
                log_header="============= DOMAINS =============",
                detailed_prompt_title=(
                    "DOMAINS: Do you wish to see the full list of failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

        if parse_requests:
            self.domain_request_changes.print_script_run_summary(
                no_changes_message="||============= No domain requests changed. =============||",
                log_header="============= DOMAIN REQUESTS =============",
                detailed_prompt_title=(
                    "DOMAIN REQUESTS: Do you wish to see the full list of failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

        if parse_managers:
            self.user_portfolio_perm_changes.print_script_run_summary(
                no_changes_message="||============= No managers changed. =============||",
                log_header="============= MANAGERS =============",
                skipped_header="----- MANAGERS SKIPPED (ALREADY EXISTED) -----",
                detailed_prompt_title=(
                    "MANAGERS: Do you wish to see the full list of failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )
            self.portfolio_invitation_changes.print_script_run_summary(
                no_changes_message="||============= No manager invitations changed. =============||",
                log_header="============= MANAGER INVITATIONS =============",
                skipped_header="----- INVITATIONS SKIPPED (ALREADY EXISTED) -----",
                detailed_prompt_title=(
                    "MANAGER INVITATIONS: Do you wish to see the full list of failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

    def create_suborganizations(self, portfolio_dict, agency_dict):
        """Create Suborganizations tied to the given portfolio based on DomainInformation objects"""
        created_suborgs = {}

        portfolios = portfolio_dict.values()
        agencies = agency_dict.values()

        domains = DomainInformation.objects.filter(
            # Org name must not be null, and must not be the portfolio name
            Q(
                organization_name__isnull=False,
            )
            & ~Q(organization_name__iexact=F("portfolio__organization_name")),
            # Only get relevant data to the agency/portfolio we are targeting
            Q(federal_agency__in=agencies) | Q(portfolio__in=portfolios),
        )
        requests = DomainRequest.objects.filter(
            # Org name must not be null, and must not be the portfolio name
            Q(
                organization_name__isnull=False,
            )
            & ~Q(organization_name__iexact=F("portfolio__organization_name")),
            # Only get relevant data to the agency/portfolio we are targeting
            Q(federal_agency__in=agencies) | Q(portfolio__in=portfolios),
        )

        # First: get all existing suborgs
        # NOTE: .all() is a heavy query, but unavoidable as we need to check for duplicate names.
        # This is not quite as heavy as just using a for loop and .get_or_create, but worth noting.
        # Change this if you can find a way to avoid doing this.
        # This won't scale great for 10k+ records.
        existing_suborgs = Suborganization.objects.all()
        suborg_dict = {normalize_string(org.name): org for org in existing_suborgs}

        # Second: Group domains and requests by normalized organization name.
        domains_dict = {}
        requests_dict = {}
        for domain in domains:
            normalized_name = normalize_string(domain.organization_name)
            domains_dict.setdefault(normalized_name, []).append(domain)

        for request in requests:
            normalized_name = normalize_string(request.organization_name)
            requests_dict.setdefault(normalized_name, []).append(request)

        # Third: Parse through each group of domains that have the same organization names,
        # then create *one* suborg record from it.
        # Normalize all suborg names so we don't add duplicate data unintentionally.
        for portfolio_name, portfolio in portfolio_dict.items():
            # For a given agency, find all domains that list suborg info for it.
            for norm_org_name, domains in domains_dict.items():
                # Don't add the record if the suborg name would equal the portfolio name
                if norm_org_name == portfolio_name:
                    continue

                new_suborg_name = None
                if len(domains) == 1:
                    new_suborg_name = normalize_string(domains[0].organization_name, lowercase=False)
                elif len(domains) > 1:
                    # Pick the best record for a suborg name (fewest spaces, most leading capitals)
                    best_record = max(
                        domains,
                        key=lambda rank: (
                            -domain.organization_name.count(" "),
                            count_capitals(domain.organization_name, leading_only=True),
                        ),
                    )
                    new_suborg_name = normalize_string(best_record.organization_name, lowercase=False)

                # If the suborg already exists, don't add it again.
                if norm_org_name not in suborg_dict and norm_org_name not in created_suborgs:
                    requests = requests_dict.get(norm_org_name)
                    suborg = Suborganization(name=new_suborg_name, portfolio=portfolio)
                    self.set_suborganization_location(suborg, domains, requests)
                    created_suborgs[norm_org_name] = suborg
        return created_suborgs

    def set_suborganization_location(self, suborg, domains, requests):
        """Updates a single suborganization's location data if valid.

        Args:
            suborg: Suborganization to update
            domains: omain info records grouped by org name
            requests: domain requests grouped by org name

        Updates are skipped if location data conflicts
        between multiple records of the same type.
        """

        # Try to get matching domain info
        domain = None
        if domains:
            reference = domains[0]
            use_location_for_domain = all(
                d.city
                and d.state_territory
                and d.city == reference.city
                and d.state_territory == reference.state_territory
                for d in domains
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

    def update_domains(self, portfolio, federal_agency, suborgs, debug):
        """
        Associate portfolio with domains for a federal agency.
        Updates all relevant domain information records.

        Returns a queryset of DomainInformation objects, or None if nothing changed.
        """
        updated_domains = set()
        domain_infos = federal_agency.domaininformation_set.all()
        for domain_info in domain_infos:
            org_name = normalize_string(domain_info.organization_name, lowercase=False)
            domain_info.portfolio = portfolio
            domain_info.sub_organization = suborgs.get(org_name, None)
            updated_domains.add(domain_info)

        if not updated_domains and debug:
            message = f"Portfolio '{portfolio}' not added to domains: nothing to add found."
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")

        return updated_domains

    def update_requests(
        self,
        portfolio,
        federal_agency,
        suborgs,
        debug,
    ):
        """
        Associate portfolio with domain requests for a federal agency.
        Updates all relevant domain request records.
        """
        updated_domain_requests = set()
        invalid_states = [
            DomainRequest.DomainRequestStatus.INELIGIBLE,
            DomainRequest.DomainRequestStatus.REJECTED,
        ]
        domain_requests = federal_agency.domainrequest_set.exclude(status__in=invalid_states)

        # Add portfolio, sub_org, requested_suborg, suborg_city, and suborg_state_territory.
        # For started domain requests, set the federal agency to None if not on a portfolio.
        for domain_request in domain_requests:
            if domain_request.status != DomainRequest.DomainRequestStatus.STARTED:
                org_name = normalize_string(domain_request.organization_name, lowercase=False)
                domain_request.portfolio = portfolio
                domain_request.sub_organization = suborgs.get(org_name, None)
                if domain_request.sub_organization is None:
                    domain_request.requested_suborganization = normalize_string(
                        domain_request.organization_name, lowercase=False
                    )
                    domain_request.suborganization_city = normalize_string(domain_request.city, lowercase=False)
                    domain_request.suborganization_state_territory = domain_request.state_territory
            else:
                # Clear the federal agency for started domain requests
                agency_name = normalize_string(domain_request.federal_agency.agency)
                portfolio_name = normalize_string(portfolio.organization_name)
                if agency_name == portfolio_name:
                    domain_request.federal_agency = None
                    logger.info(f"Set federal agency on started domain request '{domain_request}' to None.")
            updated_domain_requests.add(domain_request)

        if not updated_domain_requests and debug:
            message = f"Portfolio '{portfolio}' not added to domain requests: nothing to add found."
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")

        return updated_domain_requests

    def create_user_portfolio_permissions(self, domains):
        user_domain_roles = UserDomainRole.objects.select_related(
            "user", "domain", "domain__domain_info", "domain__domain_info__portfolio"
        ).filter(domain__in=domains, domain__domain_info__portfolio__isnull=False, role=UserDomainRole.Roles.MANAGER)
        for user_domain_role in user_domain_roles:
            user = user_domain_role.user
            permission, created = UserPortfolioPermission.objects.get_or_create(
                portfolio=user_domain_role.domain.domain_info.portfolio,
                user=user,
                defaults={
                    "roles": [UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
                    "additional_permissions": [UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS],
                },
            )
            if created:
                self.user_portfolio_perm_changes.create.append(permission)
            else:
                self.user_portfolio_perm_changes.skip.append(permission)

    def create_portfolio_invitations(self, domains):
        domain_invitations = DomainInvitation.objects.select_related(
            "domain", "domain__domain_info", "domain__domain_info__portfolio"
        ).filter(
            domain__in=domains,
            domain__domain_info__portfolio__isnull=False,
            status=DomainInvitation.DomainInvitationStatus.INVITED,
        )
        for domain_invitation in domain_invitations:
            email = normalize_string(domain_invitation.email)
            invitation, created = PortfolioInvitation.objects.get_or_create(
                portfolio=domain_invitation.domain.domain_info.portfolio,
                email=email,
                status=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
                roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
                additional_permissions=[UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS],
            )
            if created:
                self.portfolio_invitation_changes.create.append(invitation)
            else:
                self.portfolio_invitation_changes.skip.append(invitation)
