"""
This command creates and organizes federal agency portfolios by:

1. Creates a Portfolio record for the specified agencies
2. Uses fuzzy string matching to find domain requests and domain information records
   that belong to the agency (handles name variations like "Department of State" vs "State Dept" vs "DOS")
3. Automatically creates Suborganization records from the different sub-units/departments found within
   the discovered domains/requests (e.g., "IT Department", "Communications Office")
4. Associates / Links domains and requests to their proper portfolio and suborganization hierarchy

Usage Examples:
 # Create portfolio for specific agency
 ./manage.py create_federal_portfolio --agency_name "Department of State" --parse_requests --parse_domains

 # Create portfolios for entire branch
 ./manage.py create_federal_portfolio --branch "executive" --parse_requests --parse_domains

 # Dry run to see what would change
 ./manage.py create_federal_portfolio --agency_name "Department of Defense" --parse_requests --dry_run
"""

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
from registrar.management.commands.utility.fuzzy_string_matcher import create_federal_agency_matcher

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
        self.fuzzy_matcher = None
        self.fuzzy_threshold = 85
        self.dry_run = False

    def _create_fuzzy_organization_filter(self, federal_agency, all_org_names=None):
        """
        Create a Q filter that includes both direct federal agency matches
        and fuzzy organization name matches.
        """
        # Direct federal agency relationship (existing logic)
        base_filter = Q(federal_agency=federal_agency)

        # Fuzzy organization name matching
        if all_org_names and self.fuzzy_matcher:
            # The fuzzy matcher returns a MatchResult object, not a set
            match_result = self.fuzzy_matcher.find_matches(federal_agency.agency, all_org_names)

            # Extract the matched_strings from the MatchResult
            matched_org_names = match_result.matched_strings

            # Create Q objects for organization name matching
            org_name_filters = Q()
            for name in matched_org_names:
                org_name_filters |= Q(organization_name__iexact=name)

            return base_filter | org_name_filters

        return base_filter

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
            --dry_run: Show what would be changed without making any database modifications
            --fuzzy_threshold: Similarity threshold for fuzzy matching (default: 85)
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
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            help="Show what would be changed without making any database modifications.",
        )
        parser.add_argument(
            "--fuzzy_threshold",
            type=int,
            default=85,
            help="Similarity threshold for fuzzy matching (0-100, default: 85).",
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
        dry_run = options.get("dry_run")
        debug = options.get("debug")
        fuzzy_threshold = options.get("fuzzy_threshold", 85)
        self.dry_run = dry_run

        # Parse script params
        if not (parse_requests or parse_domains or parse_managers):
            raise CommandError(
                "You must specify at least one of --parse_requests, --parse_domains, or --parse_managers."
            )

        # Show dry run
        if dry_run:
            logger.info(f"{TerminalColors.BOLD}{TerminalColors.OKBLUE}")
            logger.info("=" * 60)
            logger.info("                    DRY RUN MODE")
            logger.info("          NO DATABASE CHANGES WILL BE MADE")
            logger.info("=" * 60)
            logger.info(f"{TerminalColors.ENDC}")

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

        self.fuzzy_matcher = create_federal_agency_matcher(threshold=fuzzy_threshold)

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
                    creator=User.get_default_user(),
                    notes="Auto-generated record",
                    senior_official=federal_agency.so_federal_agency.first(),
                )
                self.portfolio_changes.create.append(portfolio)
                self._log_action("CREATE", f"portfolio '{portfolio}'")
            elif skip_existing_portfolios:
                message = f"Portfolio '{portfolio}' already exists. Skipped."
                logger.info(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
                self.portfolio_changes.skip.append(portfolio)

        # Create portfolios
        if not self.dry_run:
            self.portfolio_changes.bulk_create()

        if self.dry_run:
            portfolios_to_use = list(self.portfolio_changes.create)
            if not skip_existing_portfolios:
                portfolios_to_use.extend(list(existing_portfolios))
        else:
            # After create, get the list of all portfolios to use
            portfolios_to_use = set(self.portfolio_changes.create)
            if not skip_existing_portfolios:
                portfolios_to_use.update(set(existing_portfolios))

        portfolios_to_use_dict = {normalize_string(p.organization_name): p for p in portfolios_to_use}

        # == Handle suborganizations == #
        created_suborgs = self.create_suborganizations(portfolios_to_use_dict, agencies_dict)
        if created_suborgs:
            self.suborganization_changes.create.extend(created_suborgs.values())
            if not self.dry_run:
                self.suborganization_changes.bulk_create()

        # == Handle domains and requests == #
        for portfolio_org_name, portfolio in portfolios_to_use_dict.items():
            federal_agency = agencies_dict.get(portfolio_org_name)
            suborgs = self._get_suborgs_for_portfolio(portfolio, created_suborgs)

            if parse_domains:
                updated_domains = self.update_domains(portfolio, federal_agency, suborgs, debug)
                self.domain_info_changes.update.extend(updated_domains)

            if parse_requests:
                updated_domain_requests = self.update_requests(portfolio, federal_agency, suborgs, debug)
                self.domain_request_changes.update.extend(updated_domain_requests)

        # Update DomainInformation
        if not self.dry_run:
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
            if self.dry_run:
                # In dry run mode, we can't filter by portfolios_to_use since they're not saved
                # So we need to get domains from the domain_infos that were identified for updates
                domains = []
                for domain_info in self.domain_info_changes.update:
                    try:
                        domain = Domain.objects.get(domain_info=domain_info)
                        domains.append(domain)
                    except Domain.DoesNotExist:
                        continue
                logger.info(f"Found {len(domains)} domains for manager processing in dry run mode")
            else:
                domain_infos = DomainInformation.objects.filter(portfolio__in=portfolios_to_use)
                domains = Domain.objects.filter(domain_info__in=domain_infos)

            # Create UserPortfolioPermission
            self.create_user_portfolio_permissions(domains)

            # Create PortfolioInvitation
            self.create_portfolio_invitations(domains)

        # == PRINT RUN SUMMARY == #
        self.print_final_run_summary(parse_domains, parse_requests, parse_managers, debug)

    def print_final_run_summary(self, parse_domains, parse_requests, parse_managers, debug):
        action_prefix = "WOULD BE " if self.dry_run else ""

        self.portfolio_changes.print_script_run_summary(
            no_changes_message=(f"||============= No portfolios {action_prefix.lower()}changed. =============||"),
            log_header=f"============= PORTFOLIOS {action_prefix}=============",
            skipped_header=(
                f"----- SOME PORTFOLIOS {action_prefix}WERENT CREATED " f"(BUT OTHER RECORDS ARE STILL PROCESSED) -----"
            ),
            detailed_prompt_title=(
                f"PORTFOLIOS: Do you wish to see the full list of "
                f"{action_prefix.lower()}failed, skipped and updated records?"
            ),
            display_as_str=True,
            debug=debug,
        )

        self.suborganization_changes.print_script_run_summary(
            no_changes_message=(f"||============= No suborganizations {action_prefix.lower()}changed. =============||"),
            log_header=f"============= SUBORGANIZATIONS {action_prefix}=============",
            skipped_header=(f"----- SUBORGANIZATIONS {action_prefix}SKIPPED (SAME NAME AS PORTFOLIO NAME) -----"),
            detailed_prompt_title=(
                f"SUBORGANIZATIONS: Do you wish to see the full list of "
                f"{action_prefix.lower()}failed, skipped and updated records?"
            ),
            display_as_str=True,
            debug=debug,
        )

        if parse_domains:
            self.domain_info_changes.print_script_run_summary(
                no_changes_message=(f"||============= No domains {action_prefix.lower()}changed. =============||"),
                log_header=f"============= DOMAINS {action_prefix}=============",
                detailed_prompt_title=(
                    f"DOMAINS: Do you wish to see the full list of "
                    f"{action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

        if parse_requests:
            self.domain_request_changes.print_script_run_summary(
                no_changes_message=(
                    f"||============= No domain requests {action_prefix.lower()}changed. =============||"
                ),
                log_header=f"============= DOMAIN REQUESTS {action_prefix}=============",
                detailed_prompt_title=(
                    f"DOMAIN REQUESTS: Do you wish to see the full list of "
                    f"{action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

        if parse_managers:
            self.user_portfolio_perm_changes.print_script_run_summary(
                no_changes_message=(f"||============= No managers {action_prefix.lower()}changed. =============||"),
                log_header=f"============= MANAGERS {action_prefix}=============",
                skipped_header=f"----- MANAGERS {action_prefix}SKIPPED (ALREADY EXISTED) -----",
                detailed_prompt_title=(
                    f"MANAGERS: Do you wish to see the full list of "
                    f"{action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

            self.portfolio_invitation_changes.print_script_run_summary(
                no_changes_message=(
                    f"||============= No manager invitations {action_prefix.lower()}changed. =============||"
                ),
                log_header=f"============= MANAGER INVITATIONS {action_prefix}=============",
                skipped_header=f"----- INVITATIONS {action_prefix}SKIPPED (ALREADY EXISTED) -----",
                detailed_prompt_title=(
                    f"MANAGER INVITATIONS: Do you wish to see the full list of "
                    f"{action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

        # Add dry run summary at the end
        if self.dry_run:
            self._print_dry_run_summary()

    def _print_dry_run_summary(self):
        """Print a summary of what would be changed in dry run mode."""
        logger.info(f"\n{TerminalColors.BOLD}{TerminalColors.OKBLUE}")
        logger.info("=" * 60)
        logger.info("                  DRY RUN SUMMARY")
        logger.info("=" * 60)
        logger.info(f"{TerminalColors.ENDC}")

        total_changes = (
            len(self.portfolio_changes.create)
            + len(self.suborganization_changes.create)
            + len(self.domain_info_changes.update)
            + len(self.domain_request_changes.update)
            + len(self.user_portfolio_perm_changes.create)
            + len(self.portfolio_invitation_changes.create)
        )

        logger.info(f"Total records that would be modified: {total_changes}")
        logger.info(f"  • Portfolios created: {len(self.portfolio_changes.create)}")
        logger.info(f"  • Suborganizations created: {len(self.suborganization_changes.create)}")
        logger.info(f"  • Domain infos updated: {len(self.domain_info_changes.update)}")
        logger.info(f"  • Domain requests updated: {len(self.domain_request_changes.update)}")
        logger.info(f"  • User permissions created: {len(self.user_portfolio_perm_changes.create)}")
        logger.info(f"  • Portfolio invitations created: {len(self.portfolio_invitation_changes.create)}")

        logger.info(
            f"\n{TerminalColors.BOLD}To apply these changes, run the command without --dry_run{TerminalColors.ENDC}"
        )

    def create_suborganizations(self, portfolio_dict, agency_dict):
        """Create Suborganizations tied to the given portfolio based on DomainInformation objects"""
        created_suborgs = {}

        # Get filtered domains and requests
        domains_dict, requests_dict = self._get_filtered_domains_and_requests(agency_dict)

        # Process each portfolio
        for portfolio_name, portfolio in portfolio_dict.items():
            existing_suborgs = self._get_existing_suborgs_for_portfolio(portfolio)
            portfolio_created_suborgs = self._get_portfolio_created_suborgs(created_suborgs, portfolio)

            # Create suborganizations for this portfolio
            self._create_suborgs_for_portfolio(
                portfolio_name,
                portfolio,
                domains_dict,
                requests_dict,
                existing_suborgs,
                portfolio_created_suborgs,
                created_suborgs,
            )

        return created_suborgs

    def _get_filtered_domains_and_requests(self, agency_dict):
        """Get domains and requests filtered by agencies, grouped by normalized organization name."""
        agencies = agency_dict.values()

        # Get all organization names for matching
        all_org_names = self._get_all_organization_names()

        # Build filters for domains and requests
        domain_filters, request_filters = self._build_agency_filters(agencies, all_org_names)

        # Get filtered querysets
        domains = self._get_filtered_domains(domain_filters)
        requests = self._get_filtered_requests(request_filters)

        # Group by normalized organization name
        domains_dict = self._group_by_normalized_org_name(domains, "organization_name")
        requests_dict = self._group_by_normalized_org_name(requests, "organization_name")

        return domains_dict, requests_dict

    def _get_all_organization_names(self):
        """Get all unique organization names from domains and requests."""
        domain_names = list(
            DomainInformation.objects.filter(organization_name__isnull=False)
            .values_list("organization_name", flat=True)
            .distinct()
        )
        request_names = list(
            DomainRequest.objects.filter(organization_name__isnull=False)
            .values_list("organization_name", flat=True)
            .distinct()
        )
        return [normalize_string(name) for name in domain_names + request_names]

    def _build_agency_filters(self, agencies, all_org_names):
        """Build Q filters for domains and requests based on agencies."""
        domain_filters = Q()
        request_filters = Q()

        for agency in agencies:
            agency_filter = self._create_fuzzy_organization_filter(agency, all_org_names)
            domain_filters |= agency_filter
            request_filters |= agency_filter

        return domain_filters, request_filters

    def _get_filtered_domains(self, domain_filters):
        """Get filtered domain information objects."""
        return DomainInformation.objects.filter(
            Q(organization_name__isnull=False) & ~Q(organization_name__iexact=F("portfolio__organization_name")),
            domain_filters,
        )

    def _get_filtered_requests(self, request_filters):
        """Get filtered domain request objects."""
        return DomainRequest.objects.filter(
            Q(organization_name__isnull=False) & ~Q(organization_name__iexact=F("portfolio__organization_name")),
            request_filters,
        )

    def _group_by_normalized_org_name(self, queryset, org_name_field):
        """Group queryset objects by normalized organization name."""
        grouped_dict = {}
        for obj in queryset:
            org_name = getattr(obj, org_name_field)
            normalized_name = normalize_string(org_name)
            grouped_dict.setdefault(normalized_name, []).append(obj)
        return grouped_dict

    def _get_existing_suborgs_for_portfolio(self, portfolio):
        """Get existing suborganizations for a portfolio."""
        if not portfolio.pk:
            return {}

        existing_suborgs = portfolio.portfolio_suborganizations.all()
        return {normalize_string(org.name): org for org in existing_suborgs}

    def _get_portfolio_created_suborgs(self, created_suborgs, portfolio):
        """Get suborganizations created in this batch for the given portfolio."""
        portfolio_created_suborgs = {}
        for comp_key, suborg in created_suborgs.items():
            if suborg.portfolio == portfolio and ":" in comp_key:
                norm_name = comp_key.split(":", 1)[1]
                portfolio_created_suborgs[norm_name] = suborg
        return portfolio_created_suborgs

    def _create_suborgs_for_portfolio(
        self,
        portfolio_name,
        portfolio,
        domains_dict,
        requests_dict,
        existing_suborgs,
        portfolio_created_suborgs,
        created_suborgs,
    ):
        """Create suborganizations for a specific portfolio."""
        for norm_org_name, domains in domains_dict.items():
            # Skip if suborg name would equal portfolio name
            if norm_org_name == portfolio_name:
                continue

            # Skip if suborg already exists
            if self._suborg_already_exists(norm_org_name, existing_suborgs, portfolio_created_suborgs):
                continue

            # Create new suborganization
            suborg = self._create_new_suborganization(norm_org_name, domains, requests_dict, portfolio)

            # Add to created suborgs with composite key
            portfolio_identifier = portfolio.pk if portfolio.pk else id(portfolio)
            composite_key = f"{portfolio_identifier}:{norm_org_name}"
            created_suborgs[composite_key] = suborg

            self._log_action("CREATE", f"suborganization '{suborg}' for portfolio '{portfolio}'")

    def _suborg_already_exists(self, norm_org_name, existing_suborgs, portfolio_created_suborgs):
        """Check if suborganization already exists in portfolio."""
        if norm_org_name in existing_suborgs:
            existing_suborg = existing_suborgs[norm_org_name]
            self._log_action(
                "SKIP", f"suborganization '{existing_suborg}' already exists in portfolio '{existing_suborg.portfolio}'"
            )
            return True

        return norm_org_name in portfolio_created_suborgs

    def _create_new_suborganization(self, norm_org_name, domains, requests_dict, portfolio):
        """Create a new suborganization object."""
        suborg_name = self._determine_best_suborg_name(domains)
        requests = requests_dict.get(norm_org_name)

        suborg = Suborganization(name=suborg_name, portfolio=portfolio)
        self.set_suborganization_location(suborg, domains, requests)

        return suborg

    def _determine_best_suborg_name(self, domains):
        """Determine the best name for a suborganization from domain records."""
        if len(domains) == 1:
            return normalize_string(domains[0].organization_name, lowercase=False)

        # Pick the best record (fewest spaces, most leading capitals)
        best_record = max(
            domains,
            key=lambda domain: (
                -domain.organization_name.count(" "),
                count_capitals(domain.organization_name, leading_only=True),
            ),
        )
        return normalize_string(best_record.organization_name, lowercase=False)

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
        # Get all domain organization names
        all_domain_org_names = list(DomainInformation.objects.values_list("organization_name", flat=True).distinct())
        # Use fuzzy matching to find domain information records that belong to this agency
        # This creates a filter that matches domains in two ways:
        # 1. Direct relationship: domains already linked to this federal agency
        # 2. Fuzzy name matching: domains with organization names that are similar
        #    to this agency's name (handles abbreviations, variations, etc.)
        #
        # e.g., if federal_agency is "Department of Defense", this will find:
        # - Domains already linked to DoD (direct relationship)
        # - Domains with org names like "DoD", "Defense Dept", "US Dept of Defense" (fuzzy matching)
        # - This helps capture domains that should belong to this agency but weren't
        #   properly linked due to name variations in the organization_name field
        domain_filter = self._create_fuzzy_organization_filter(
            federal_agency, [normalize_string(name) for name in all_domain_org_names if name]
        )
        domain_infos = DomainInformation.objects.filter(domain_filter)

        if debug:
            logger.info(
                f"Fuzzy matching found {domain_infos.count()} domain information records for '{federal_agency.agency}'"
            )

        for domain_info in domain_infos:
            org_name = normalize_string(domain_info.organization_name)
            new_suborg = suborgs.get(org_name, None)

            # ADD DRY RUN CHANGE TRACKING:
            changes = []
            if domain_info.portfolio != portfolio:
                changes.append(f"portfolio: {domain_info.portfolio} → {portfolio}")
            if domain_info.sub_organization != new_suborg:
                changes.append(f"sub_organization: {domain_info.sub_organization} → {new_suborg}")

            # Log changes in dry run mode
            self._log_changes(f"domain '{domain_info.domain}'", changes)

            # Apply changes (these will still be tracked but not saved in dry run)
            domain_info.portfolio = portfolio
            domain_info.sub_organization = new_suborg
            updated_domains.add(domain_info)

        if not updated_domains and debug:
            message = f"Portfolio '{portfolio}' not added to domains: nothing to add found."
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")

        return updated_domains

    def update_requests(self, portfolio, federal_agency, suborgs, debug):
        """
        Associate portfolio with domain requests for a federal agency.
        Updates all relevant domain request records.
        """
        updated_domain_requests = set()
        invalid_states = [
            DomainRequest.DomainRequestStatus.INELIGIBLE,
            DomainRequest.DomainRequestStatus.REJECTED,
        ]

        # Get all request organization names for fuzzy matching
        all_request_org_names = list(
            DomainRequest.objects.exclude(status__in=invalid_states)
            .values_list("organization_name", flat=True)
            .distinct()
        )

        # Use fuzzy matching to find domain requests that belong to this agency
        request_filter = self._create_fuzzy_organization_filter(
            federal_agency, [normalize_string(name) for name in all_request_org_names if name]
        )
        domain_requests = DomainRequest.objects.filter(request_filter).exclude(status__in=invalid_states)

        if debug:
            logger.info(f"Fuzzy matching found {domain_requests.count()} domain requests for '{federal_agency.agency}'")

        # Process each domain request
        for domain_request in domain_requests:
            if domain_request.status != DomainRequest.DomainRequestStatus.STARTED:
                self._update_active_request(domain_request, portfolio, suborgs)
            else:
                self._handle_started_request(domain_request, portfolio)
            updated_domain_requests.add(domain_request)

        if not updated_domain_requests and debug:
            message = f"Portfolio '{portfolio}' not added to domain requests: nothing to add found."
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")

        return updated_domain_requests

    def _update_active_request(self, domain_request, portfolio, suborgs):
        """Update an active (non-started) domain request."""
        org_name = normalize_string(domain_request.organization_name)
        new_suborg = suborgs.get(org_name, None)

        # Track changes for dry run
        changes = []
        if domain_request.portfolio != portfolio:
            changes.append(f"portfolio: {domain_request.portfolio} → {portfolio}")
        if domain_request.sub_organization != new_suborg:
            changes.append(f"sub_organization: {domain_request.sub_organization} → {new_suborg}")

        # Log changes in dry run mode
        self._log_changes(f"request '{domain_request}'", changes)

        # Apply changes
        domain_request.portfolio = portfolio
        domain_request.sub_organization = new_suborg

        if domain_request.sub_organization is None:
            domain_request.requested_suborganization = normalize_string(
                domain_request.organization_name, lowercase=False
            )
            domain_request.suborganization_city = normalize_string(domain_request.city, lowercase=False)
            domain_request.suborganization_state_territory = domain_request.state_territory

    def _handle_started_request(self, domain_request, portfolio):
        """Handle started domain requests by clearing federal agency if needed."""
        if not domain_request.federal_agency:
            return

        agency_name = normalize_string(domain_request.federal_agency.agency)
        portfolio_name = normalize_string(portfolio.organization_name)

        if agency_name == portfolio_name:
            if self.dry_run:
                logger.info(f"WOULD SET federal agency on started domain request '{domain_request}' to None.")
            else:
                domain_request.federal_agency = None
                logger.info(f"Set federal agency on started domain request '{domain_request}' to None.")

    def create_user_portfolio_permissions(self, domains):
        """
        Ensures domain managers retain their VIEW_MANAGED_DOMAINS permission
        when portfolios are created or updated.

        Args:
            domains: List of Domain objects that belong to portfolios being processed
        """
        if not domains:
            logger.info("No domains found for portfolio permission processing")
            return

        logger.info(f"Processing {len(domains)} domains for user portfolio permissions")
        user_domain_roles = UserDomainRole.objects.select_related(
            "user", "domain", "domain__domain_info", "domain__domain_info__portfolio"
        ).filter(domain__in=domains, domain__domain_info__portfolio__isnull=False, role=UserDomainRole.Roles.MANAGER)

        if not user_domain_roles.exists():
            logger.info("No domain managers found for the provided domains")
            return

        logger.info(f"Found {user_domain_roles.count()} domain manager roles to process")

        for user_domain_role in user_domain_roles:
            self._process_manager_role(user_domain_role)

    def _find_domains_using_fuzzy_matching(self):
        """Find domains using the same fuzzy matching logic as update_domains() - dry run only."""
        if self.domain_info_changes.update:
            domains = []
            for domain_info in self.domain_info_changes.update:
                try:
                    domain = Domain.objects.get(domain_info=domain_info)
                    domains.append(domain)
                except Domain.DoesNotExist:
                    continue

            logger.info(f"Found {len(domains)} domains from domain_info updates for dry run")
            return domains

        logger.info("No domain info updates found, no domains to process for permissions")
        return []

    def _process_manager_role(self, user_domain_role):
        """Process a single domain manager role."""
        user = user_domain_role.user
        domain = user_domain_role.domain
        domain_name = domain.name

        if self.dry_run:
            portfolio = self._find_new_portfolio_for_domain(domain)
        else:
            if domain.domain_info and domain.domain_info.portfolio:
                portfolio = domain.domain_info.portfolio

        if not portfolio:
            logger.warning(f"Could not determine portfolio for domain {domain_name}")
            return

        logger.info(f"Processing manager {user.email} for domain {domain_name} in portfolio '{portfolio}'")
        self._ensure_manager_portfolio_permission(user, portfolio)

    def _find_new_portfolio_for_domain(self, domain):
        """Find which portfolio a domain will be assigned to in dry run mode."""
        for domain_info in self.domain_info_changes.update:
            if domain_info.domain == domain:
                return domain_info.portfolio

        return self._find_portfolio_for_domain(domain)

    def _find_portfolio_for_domain(self, domain):
        """Find which portfolio a domain belongs to using fuzzy matching."""
        if not domain.domain_info or not domain.domain_info.organization_name:
            return None

        domain_org_name = domain.domain_info.organization_name
        portfolios_to_process = list(self.portfolio_changes.create) + list(self.portfolio_changes.skip)

        for portfolio in portfolios_to_process:
            if portfolio.federal_agency:
                domain_filter = self._create_fuzzy_organization_filter(
                    portfolio.federal_agency, [normalize_string(domain_org_name)]
                )

                if DomainInformation.objects.filter(id=domain.domain_info.id).filter(domain_filter).exists():
                    return portfolio

        return None

    def _ensure_manager_portfolio_permission(self, user, portfolio):
        """Ensure a domain manager has the correct portfolio permissions."""
        defaults = {
            "roles": [UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            "additional_permissions": [UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS],
        }

        if self.dry_run:
            self._handle_dry_run_permission(user, portfolio, defaults)
        else:
            self._handle_live_permission(user, portfolio, defaults)

    def _handle_dry_run_permission(self, user, portfolio, defaults):
        """Handle permission processing in dry run mode."""
        try:
            existing_permission = UserPortfolioPermission.objects.get(portfolio=portfolio, user=user)

            current_roles = existing_permission.roles or []
            current_perms = existing_permission.additional_permissions or []

            needs_update = (
                UserPortfolioRoleChoices.ORGANIZATION_MEMBER in current_roles
                and UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS not in current_perms
            )

            if needs_update:
                new_perms = current_perms + [UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS]
                changes = [f"additional_permissions: {current_perms} → {new_perms}"]
                self._log_changes(f"user portfolio permission for {user.email} in portfolio '{portfolio}'", changes)
                mock_permission = self._create_mock_permission(
                    user,
                    portfolio,
                    current_roles,
                    current_perms + [UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS],
                )
                self.user_portfolio_perm_changes.update.append(mock_permission)
            else:
                self._log_action(
                    "SKIP", f"user portfolio permission for {user.email} in portfolio '{portfolio}' (already correct)"
                )
                mock_permission = self._create_mock_permission(user, portfolio, current_roles, current_perms)
                self.user_portfolio_perm_changes.skip.append(mock_permission)

        except UserPortfolioPermission.DoesNotExist:
            self._log_action(
                "CREATE",
                f"user portfolio permission for {user.email} in portfolio '{portfolio}' with manager permissions",
            )
            mock_permission = self._create_mock_permission(
                user, portfolio, defaults["roles"], defaults["additional_permissions"]
            )
            self.user_portfolio_perm_changes.create.append(mock_permission)

    def _handle_live_permission(self, user, portfolio, defaults):
        """Handle permission processing in live mode."""
        permission, created = UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio, user=user, defaults=defaults
        )

        if created:
            self._log_action("CREATE", f"user portfolio permission for {user.email} in portfolio '{portfolio}'")
            self.user_portfolio_perm_changes.create.append(permission)
        elif UserPortfolioRoleChoices.ORGANIZATION_MEMBER in (
            permission.roles or []
        ) and UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS not in (permission.additional_permissions or []):

            additional_perms = (permission.additional_permissions or []).copy()
            additional_perms.append(UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS)
            permission.additional_permissions = additional_perms
            permission.save()

            self._log_action(
                "UPDATE",
                f"user portfolio permission for {user.email} in portfolio '{portfolio}' - added VIEW_MANAGED_DOMAINS",
            )
            self.user_portfolio_perm_changes.update.append(permission)
        else:
            self._log_action(
                "SKIP", f"user portfolio permission for {user.email} in portfolio '{portfolio}' (already correct)"
            )
            self.user_portfolio_perm_changes.skip.append(permission)

    def _create_mock_permission(self, user, portfolio, roles, additional_permissions):
        """Create a mock permission object for dry run tracking."""

        class MockPermission:
            def __init__(self, user, portfolio, roles, additional_permissions):
                self.user = user
                self.portfolio = portfolio
                self.roles = roles
                self.additional_permissions = additional_permissions

            def __str__(self):
                return f"UserPortfolioPermission for {self.user.email} in {self.portfolio}"

        return MockPermission(user, portfolio, roles, additional_permissions)

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
            )
            if created:
                self.portfolio_invitation_changes.create.append(invitation)
            else:
                self.portfolio_invitation_changes.skip.append(invitation)

    def _log_action(self, action_type, obj, message=None):
        """
        Log an action that would be performed, with dry run support.

        Args:
            action_type: Type of action ('CREATE', 'UPDATE', 'DELETE')
            obj: Object being acted upon
            message: Optional custom message
        """
        action_text = f"WOULD {action_type}" if self.dry_run else action_type.title()
        obj_repr = message or str(obj)

        color = TerminalColors.OKGREEN
        if action_type == "UPDATE":
            color = TerminalColors.YELLOW
        elif action_type == "DELETE":
            color = TerminalColors.FAIL

        logger.info(f"{color}{action_text} {obj_repr}{TerminalColors.ENDC}")

    def _log_changes(self, obj, changes):
        """Log what changes would be made to an object in dry run mode."""
        if self.dry_run and changes:
            logger.info(f"  WOULD UPDATE {obj}: {', '.join(changes)}")

    def _get_suborgs_for_portfolio(self, portfolio, created_suborgs):
        """Get all suborganizations for a portfolio"""
        suborgs = {}

        # Always add just-created suborganizations
        if created_suborgs:
            for composite_key, suborg in created_suborgs.items():
                if suborg.portfolio == portfolio:
                    suborgs[normalize_string(suborg.name)] = suborg

        # In normal execution, also add existing suborganizations from the database
        if not self.dry_run:
            for suborg in portfolio.portfolio_suborganizations.all():
                normalized_name = normalize_string(suborg.name)
                if normalized_name not in suborgs:  # Don't overwrite just-created ones
                    suborgs[normalized_name] = suborg

        return suborgs
