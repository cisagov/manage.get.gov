"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from collections import defaultdict
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

        # Add dry run support
        self.dry_run = False
        self.match_report = defaultdict(list)

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
            --test_fuzzy_matching: Test and display fuzzy matching results without any other operations
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
            "--test_fuzzy_matching",
            action=argparse.BooleanOptionalAction,
            help="Test and display fuzzy matching results without any other operations.",
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
        test_fuzzy_matching = options.get("test_fuzzy_matching")
        fuzzy_threshold = options.get("fuzzy_threshold", 85)
        debug = options.get("debug")
        self.dry_run = dry_run or test_fuzzy_matching
        self.fuzzy_threshold = fuzzy_threshold
        if test_fuzzy_matching:
            self.test_fuzzy_matching_only(agency_name, branch, debug)
            return

        # Parse script params
        if not (parse_requests or parse_domains or parse_managers):
            raise CommandError(
                "You must specify at least one of --parse_requests, --parse_domains, or --parse_managers."
            )

        # Show dry run warning
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
                action_text = "WOULD CREATE" if dry_run else "Created"
                logger.info(f"{TerminalColors.OKGREEN}{action_text} portfolio '{portfolio}'.{TerminalColors.ENDC}")
            elif skip_existing_portfolios:
                message = f"Portfolio '{portfolio}' already exists. Skipped."
                logger.info(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")
                self.portfolio_changes.skip.append(portfolio)

        # Create portfolios (skip in dry run)
        if not dry_run:
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
            if not dry_run:
                self.suborganization_changes.bulk_create()

        # == Handle domains and requests == #
        for portfolio_org_name, portfolio in portfolios_to_use_dict.items():
            federal_agency = agencies_dict.get(portfolio_org_name)
            suborgs = {}
            if not dry_run:
                suborgs = portfolio.portfolio_suborganizations.in_bulk(field_name="name")

            if parse_domains:
                updated_domains = self.update_domains(portfolio, federal_agency, suborgs, debug)
                self.domain_info_changes.update.extend(updated_domains)

            if parse_requests:
                updated_domain_requests = self.update_requests(portfolio, federal_agency, suborgs, debug)
                self.domain_request_changes.update.extend(updated_domain_requests)

        # Update records (skip in dry run)
        if not dry_run:
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

        if dry_run:
            self.print_dry_run_summary()

    def test_fuzzy_matching_only(self, agency_name, branch, debug):
        """Test mode only shows fuzzy matching results without any database modifications."""
        logger.info(f"{TerminalColors.BOLD}{TerminalColors.OKBLUE}")
        logger.info("=" * 70)
        logger.info("                    FUZZY MATCHING TEST MODE")
        logger.info("=" * 70)
        logger.info(f"{TerminalColors.ENDC}")

        # Get agencies
        federal_agency_filter = {"agency__iexact": agency_name} if agency_name else {"federal_type": branch}
        agencies = FederalAgency.objects.filter(agency__isnull=False, **federal_agency_filter).distinct()

        if not agencies.exists():
            logger.error("No agencies found!")
            return

        # Get all organization names from requests and domains
        all_request_org_names = list(DomainRequest.objects.values_list("organization_name", flat=True).distinct())
        all_domain_org_names = list(DomainInformation.objects.values_list("organization_name", flat=True).distinct())

        # Test fuzzy matching for each agency
        for agency in agencies:
            logger.info(f"\n{TerminalColors.HEADER}Testing matches for: {agency.agency}{TerminalColors.ENDC}")
            logger.info("-" * 50)

            # Test request matches
            request_matches = self._get_fuzzy_organization_matches(
                agency.agency,
                [normalize_string(name) for name in all_request_org_names if name],
                threshold=self.fuzzy_threshold,
            )

            # Test domain matches
            domain_matches = self._get_fuzzy_organization_matches(
                agency.agency,
                [normalize_string(name) for name in all_domain_org_names if name],
                threshold=self.fuzzy_threshold,
            )

            # Results
            logger.info(
                f"{TerminalColors.OKGREEN}Request organization matches ({len(request_matches)}):{TerminalColors.ENDC}"
            )
            for match in sorted(request_matches)[:10]:  # Show top 10
                count = DomainRequest.objects.filter(organization_name__iexact=match).count()
                logger.info(f"  • {match} ({count} requests)")

            if len(request_matches) > 10:
                logger.info(f"  ... and {len(request_matches) - 10} more")

            logger.info(
                f"\n{TerminalColors.OKGREEN}Domain organization matches ({len(domain_matches)}):{TerminalColors.ENDC}"
            )
            for match in sorted(domain_matches)[:10]:  # Show top 10
                count = DomainInformation.objects.filter(organization_name__iexact=match).count()
                logger.info(f"  • {match} ({count} domains)")

            if len(domain_matches) > 10:
                logger.info(f"  ... and {len(domain_matches) - 10} more")

            # Show potential new matches (those not directly related to the agency)
            current_requests = (
                DomainRequest.objects.filter(federal_agency=agency)
                .values_list("organization_name", flat=True)
                .distinct()
            )
            current_domains = (
                DomainInformation.objects.filter(federal_agency=agency)
                .values_list("organization_name", flat=True)
                .distinct()
            )

            new_request_matches = request_matches - set([normalize_string(name) for name in current_requests if name])
            new_domain_matches = domain_matches - set([normalize_string(name) for name in current_domains if name])

            if new_request_matches:
                logger.info(
                    f"\n{TerminalColors.YELLOW}NEW request matches found ({len(new_request_matches)}):{TerminalColors.ENDC}"
                )
                for match in sorted(new_request_matches)[:5]:
                    count = DomainRequest.objects.filter(organization_name__iexact=match).count()
                    logger.info(f"  • {match} ({count} requests)")

            if new_domain_matches:
                logger.info(
                    f"\n{TerminalColors.YELLOW}NEW domain matches found ({len(new_domain_matches)}):{TerminalColors.ENDC}"
                )
                for match in sorted(new_domain_matches)[:5]:
                    count = DomainInformation.objects.filter(organization_name__iexact=match).count()
                    logger.info(f"  • {match} ({count} domains)")

        logger.info(
            f"\n{TerminalColors.BOLD}Test completed! Use --dry_run with other flags to see what would change.{TerminalColors.ENDC}"
        )

    def print_dry_run_summary(self):
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

        if self.match_report:
            logger.info(f"\n{TerminalColors.HEADER}Fuzzy Matching Report:{TerminalColors.ENDC}")
            for agency_name, matches in self.match_report.items():
                logger.info(f"\n{agency_name}:")
                for match_info in matches[:5]:  # Shows top 5
                    logger.info(f"  • {match_info}")

        logger.info(
            f"\n{TerminalColors.BOLD}To apply these changes, run the command without --dry_run{TerminalColors.ENDC}"
        )

    def _get_fuzzy_organization_matches(self, target_agency_name, candidate_org_names, threshold=85):
        """
        Use RapidFuzz to find organization names that closely match the target agency.

        Args:
            target_agency_name: The federal agency name to match against
            candidate_org_names: List of organization names to search through
            threshold: Minimum similarity score (0-100) to consider a match

        Returns:
            Set of organization names that match above the threshold
        """
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            # Fallback to basic variants if rapidfuzz is not available
            logger.warning("RapidFuzz not available, falling back to basic matching")
            return self._get_organization_name_variants(target_agency_name)

        normalized_target = normalize_string(target_agency_name)

        # Use multiple fuzzy matching strategies for comprehensive coverage
        matched_names = set()

        # Token sort ratio (handles word order differences)
        # e.g. for "U.S. Department of State" vs "Department of State U.S."
        token_matches = process.extract(
            normalized_target,
            candidate_org_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
            limit=None,  # Get all matches above threshold
        )
        matched_names.update([match[0] for match in token_matches])

        # Token set ratio (handles extra/missing words)
        # e.g. for "Department of State" vs "U.S. Department of State"
        set_matches = process.extract(
            normalized_target, candidate_org_names, scorer=fuzz.token_set_ratio, score_cutoff=threshold, limit=None
        )
        matched_names.update([match[0] for match in set_matches])

        # Partial ratio (handles substring matches)
        # e.g. for "State Department" matching "Department of State"
        partial_matches = process.extract(
            normalized_target,
            candidate_org_names,
            scorer=fuzz.partial_ratio,
            score_cutoff=max(threshold, 90),  # Higher threshold for partial matches
            limit=None,
        )
        matched_names.update([match[0] for match in partial_matches])

        # Always include exact variants as fallback
        matched_names.update(self._get_organization_name_variants(target_agency_name))

        # Store for reporting in dry run mode
        if self.dry_run:
            self.match_report[target_agency_name].extend(
                [
                    f"{match[0]} (score: {match[1]})"
                    for match in sorted(
                        token_matches + set_matches + partial_matches, key=lambda x: x[1], reverse=True
                    )[:10]
                ]
            )

        return matched_names

    def _get_organization_name_variants(self, agency_name):
        """
        Generate common variants of federal agency names for fallback matching.
        """
        variants = {normalize_string(agency_name)}

        # Handle U.S. prefix variations
        if agency_name.startswith("U.S. "):
            variants.add(normalize_string(agency_name[4:]))
            variants.add(normalize_string("US " + agency_name[4:]))
        elif agency_name.startswith("US "):
            variants.add(normalize_string(agency_name[3:]))
            variants.add(normalize_string("U.S. " + agency_name[3:]))
        else:
            variants.add(normalize_string("U.S. " + agency_name))
            variants.add(normalize_string("US " + agency_name))

        # Handle "The" prefix and common abbreviations
        base_name = agency_name
        if base_name.startswith("The "):
            base_name = base_name[4:]
            variants.add(normalize_string(base_name))
        else:
            variants.add(normalize_string("The " + base_name))

        # Common federal agency abbreviations
        dept_variations = [
            ("Department of", "Dept of", "Dept. of"),
            ("Administration", "Admin"),
            ("Agency", "Agcy"),
        ]

        for full, *abbrevs in dept_variations:
            if full in agency_name:
                for abbrev in abbrevs:
                    variants.add(normalize_string(agency_name.replace(full, abbrev)))

        return variants

    def _create_organization_matching_filter(self, federal_agency, all_org_names=None):
        """
        Create a Q filter using fuzzy matching for organization names and federal agency relationship.

        Args:
            federal_agency: The FederalAgency instance to match
            all_org_names: Optional list of all organization names for fuzzy matching
        """
        # Start with direct federal agency relationship
        base_filter = Q(federal_agency=federal_agency)

        # Add fuzzy organization name matching
        if all_org_names:
            # Use fuzzy matching against all candidate organization names
            matched_org_names = self._get_fuzzy_organization_matches(
                federal_agency.agency, all_org_names, threshold=self.fuzzy_threshold
            )
        else:
            # Fallback to rule-based variants
            matched_org_names = self._get_organization_name_variants(federal_agency.agency)

        # Create Q objects for organization name matching (case-insensitive)
        org_name_filters = Q()
        for name in matched_org_names:
            org_name_filters |= Q(organization_name__iexact=name)

        return base_filter | org_name_filters

    def create_suborganizations(self, portfolio_dict, agency_dict):
        """Create Suborganizations tied to the given portfolio based on DomainInformation objects"""
        created_suborgs = {}

        portfolios = portfolio_dict.values()
        agencies = agency_dict.values()

        # Get all unique organization names for fuzzy matching
        all_domain_org_names = list(
            DomainInformation.objects.filter(organization_name__isnull=False)
            .values_list("organization_name", flat=True)
            .distinct()
        )

        all_request_org_names = list(
            DomainRequest.objects.filter(organization_name__isnull=False)
            .values_list("organization_name", flat=True)
            .distinct()
        )

        # Combine and normalize for fuzzy matching
        all_org_names = list(set([normalize_string(name) for name in all_domain_org_names + all_request_org_names]))

        # Create filters for flexible organization name matching
        domain_filters = Q()
        request_filters = Q()

        for agency in agencies:
            agency_filter = self._create_organization_matching_filter(agency, all_org_names)
            domain_filters |= agency_filter
            request_filters |= agency_filter

        domains = DomainInformation.objects.filter(
            # Org name must not be null, and must not be the portfolio name
            Q(
                organization_name__isnull=False,
            )
            & ~Q(organization_name__iexact=F("portfolio__organization_name")),
            # Use flexible matching for agency/organization names
            domain_filters,
        )
        requests = DomainRequest.objects.filter(
            # Org name must not be null, and must not be the portfolio name
            Q(
                organization_name__isnull=False,
            )
            & ~Q(organization_name__iexact=F("portfolio__organization_name")),
            # Use flexible matching for agency/organization names
            request_filters,
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
                    action_text = "WOULD CREATE" if self.dry_run else "Created"
                    logger.info(
                        f"{TerminalColors.OKGREEN}{action_text} suborganization '{suborg}'.{TerminalColors.ENDC}"
                    )
        return created_suborgs

    def set_suborganization_location(self, suborg, domains, requests):
        """Updates a single suborganization's location data if valid.

        Args:
            suborg: Suborganization to update
            domains: Domain info records grouped by org name
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
        Updates all relevant domain information records using fuzzy organization name matching.

        Returns a queryset of DomainInformation objects, or None if nothing changed.
        """
        updated_domains = set()

        # Get all domain organization names for fuzzy matching
        all_domain_org_names = list(DomainInformation.objects.values_list("organization_name", flat=True).distinct())

        # Use fuzzy matching for domains
        domain_filter = self._create_organization_matching_filter(federal_agency, all_domain_org_names)
        domain_infos = DomainInformation.objects.filter(domain_filter)

        if debug or self.dry_run:
            matched_org_names = self._get_fuzzy_organization_matches(
                federal_agency.agency,
                [normalize_string(name) for name in all_domain_org_names if name],
                threshold=self.fuzzy_threshold,
            )
            logger.info(f"Domain matching for '{federal_agency.agency}' found {len(matched_org_names)} name variants")
            logger.info(f"Processing {domain_infos.count()} domain information records")

        for domain_info in domain_infos:
            org_name = normalize_string(domain_info.organization_name, lowercase=False)

            # Show what would change in dry run
            if self.dry_run:
                current_portfolio = domain_info.portfolio
                current_suborg = domain_info.sub_organization
                new_suborg = suborgs.get(org_name, None)

                changes = []
                if current_portfolio != portfolio:
                    changes.append(f"portfolio: {current_portfolio} → {portfolio}")
                if current_suborg != new_suborg:
                    changes.append(f"sub_organization: {current_suborg} → {new_suborg}")

                if changes:
                    logger.info(f"  WOULD UPDATE domain '{domain_info.domain}': {', '.join(changes)}")

            domain_info.portfolio = portfolio
            domain_info.sub_organization = suborgs.get(org_name, None)
            updated_domains.add(domain_info)

        if not updated_domains and (debug or self.dry_run):
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
        Associate portfolio with domain requests for a federal agency using fuzzy matching.
        Updates all relevant domain request records that match either by federal_agency
        relationship or by organization name fuzzy matching.
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

        # Use fuzzy matching for domain requests
        request_filter = self._create_organization_matching_filter(federal_agency, all_request_org_names)
        domain_requests = DomainRequest.objects.filter(request_filter).exclude(status__in=invalid_states)

        if debug or self.dry_run:
            # Log the fuzzy matching strategy being used
            matched_org_names = self._get_fuzzy_organization_matches(
                federal_agency.agency,
                [normalize_string(name) for name in all_request_org_names if name],
                threshold=self.fuzzy_threshold,
            )
            logger.info(f"Request matching for '{federal_agency.agency}' using {len(matched_org_names)} name variants")
            logger.info(f"Found {domain_requests.count()} domain requests to process")

            # Show some example matches for debugging
            sample_matches = list(matched_org_names)[:5]
            if sample_matches:
                logger.info(f"Example matched variants: {sample_matches}")

        # Add portfolio, sub_org, requested_suborg, suborg_city, and suborg_state_territory.
        # For started domain requests, set the federal agency to None if not on a portfolio.
        for domain_request in domain_requests:
            if domain_request.status != DomainRequest.DomainRequestStatus.STARTED:
                org_name = normalize_string(domain_request.organization_name, lowercase=False)

                # Show what would change in dry run
                if self.dry_run:
                    changes = []
                    if domain_request.portfolio != portfolio:
                        changes.append(f"portfolio: {domain_request.portfolio} → {portfolio}")

                    new_suborg = suborgs.get(org_name, None)
                    if domain_request.sub_organization != new_suborg:
                        changes.append(f"sub_organization: {domain_request.sub_organization} → {new_suborg}")

                    if domain_request.federal_agency != federal_agency:
                        changes.append(f"federal_agency: {domain_request.federal_agency} → {federal_agency}")

                    if changes:
                        logger.info(f"  WOULD UPDATE request '{domain_request}': {', '.join(changes)}")

                domain_request.portfolio = portfolio
                domain_request.sub_organization = suborgs.get(org_name, None)

                # Update federal_agency if it wasn't already set correctly
                if domain_request.federal_agency != federal_agency:
                    old_agency = domain_request.federal_agency
                    domain_request.federal_agency = federal_agency
                    if debug or self.dry_run:
                        action_text = "WOULD UPDATE" if self.dry_run else "Updated"
                        logger.info(
                            f"{action_text} federal_agency for request '{domain_request}' from "
                            f"'{old_agency}' to '{federal_agency}'"
                        )

                if domain_request.sub_organization is None:
                    domain_request.requested_suborganization = normalize_string(
                        domain_request.organization_name, lowercase=False
                    )
                    domain_request.suborganization_city = normalize_string(domain_request.city, lowercase=False)
                    domain_request.suborganization_state_territory = domain_request.state_territory
            else:
                # Clear the federal agency for started domain requests
                agency_name = normalize_string(
                    domain_request.federal_agency.agency if domain_request.federal_agency else ""
                )
                portfolio_name = normalize_string(portfolio.organization_name)
                if agency_name == portfolio_name:
                    if self.dry_run:
                        logger.info(f"WOULD SET federal agency on started domain request '{domain_request}' to None.")
                    else:
                        domain_request.federal_agency = None
                        logger.info(f"Set federal agency on started domain request '{domain_request}' to None.")
            updated_domain_requests.add(domain_request)

        if not updated_domain_requests and (debug or self.dry_run):
            message = f"Portfolio '{portfolio}' not added to domain requests: nothing to add found."
            logger.warning(f"{TerminalColors.YELLOW}{message}{TerminalColors.ENDC}")

        return updated_domain_requests

    def print_final_run_summary(self, parse_domains, parse_requests, parse_managers, debug):
        action_prefix = "WOULD BE " if self.dry_run else ""

        self.portfolio_changes.print_script_run_summary(
            no_changes_message=f"||============= No portfolios {action_prefix.lower()}changed. =============||",
            log_header=f"============= PORTFOLIOS {action_prefix}=============",
            skipped_header=f"----- SOME PORTFOLIOS {action_prefix}WERENT CREATED (BUT OTHER RECORDS ARE STILL PROCESSED) -----",
            detailed_prompt_title=(
                f"PORTFOLIOS: Do you wish to see the full list of {action_prefix.lower()}failed, skipped and updated records?"
            ),
            display_as_str=True,
            debug=debug,
        )
        self.suborganization_changes.print_script_run_summary(
            no_changes_message=f"||============= No suborganizations {action_prefix.lower()}changed. =============||",
            log_header=f"============= SUBORGANIZATIONS {action_prefix}=============",
            skipped_header=f"----- SUBORGANIZATIONS {action_prefix}SKIPPED (SAME NAME AS PORTFOLIO NAME) -----",
            detailed_prompt_title=(
                f"SUBORGANIZATIONS: Do you wish to see the full list of {action_prefix.lower()}failed, skipped and updated records?"
            ),
            display_as_str=True,
            debug=debug,
        )

        if parse_domains:
            self.domain_info_changes.print_script_run_summary(
                no_changes_message=f"||============= No domains {action_prefix.lower()}changed. =============||",
                log_header=f"============= DOMAINS {action_prefix}=============",
                detailed_prompt_title=(
                    f"DOMAINS: Do you wish to see the full list of {action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

        if parse_requests:
            self.domain_request_changes.print_script_run_summary(
                no_changes_message=f"||============= No domain requests {action_prefix.lower()}changed. =============||",
                log_header=f"============= DOMAIN REQUESTS {action_prefix}=============",
                detailed_prompt_title=(
                    f"DOMAIN REQUESTS: Do you wish to see the full list of {action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

        if parse_managers:
            self.user_portfolio_perm_changes.print_script_run_summary(
                no_changes_message=f"||============= No managers {action_prefix.lower()}changed. =============||",
                log_header=f"============= MANAGERS {action_prefix}=============",
                skipped_header=f"----- MANAGERS {action_prefix}SKIPPED (ALREADY EXISTED) -----",
                detailed_prompt_title=(
                    f"MANAGERS: Do you wish to see the full list of {action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )
            self.portfolio_invitation_changes.print_script_run_summary(
                no_changes_message=f"||============= No manager invitations {action_prefix.lower()}changed. =============||",
                log_header=f"============= MANAGER INVITATIONS {action_prefix}=============",
                skipped_header=f"----- INVITATIONS {action_prefix}SKIPPED (ALREADY EXISTED) -----",
                detailed_prompt_title=(
                    f"MANAGER INVITATIONS: Do you wish to see the full list of {action_prefix.lower()}failed, skipped and updated records?"
                ),
                display_as_str=True,
                debug=debug,
            )

    def create_user_portfolio_permissions(self, domains):
        user_domain_roles = UserDomainRole.objects.select_related(
            "user", "domain", "domain__domain_info", "domain__domain_info__portfolio"
        ).filter(domain__in=domains, domain__domain_info__portfolio__isnull=False, role=UserDomainRole.Roles.MANAGER)
        for user_domain_role in user_domain_roles:
            user = user_domain_role.user
            permission, created = UserPortfolioPermission.objects.get_or_create(
                portfolio=user_domain_role.domain.domain_info.portfolio,
                user=user,
                defaults={"roles": [UserPortfolioRoleChoices.ORGANIZATION_MEMBER]},
            )
            if created:
                self.user_portfolio_perm_changes.create.append(permission)
                action_text = "WOULD CREATE" if self.dry_run else "Created"
                logger.info(f"{action_text} user portfolio permission for {user}")
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
            )
            if created:
                self.portfolio_invitation_changes.create.append(invitation)
                action_text = "WOULD CREATE" if self.dry_run else "Created"
                logger.info(f"{action_text} portfolio invitation for {email}")
            else:
                self.portfolio_invitation_changes.skip.append(invitation)
