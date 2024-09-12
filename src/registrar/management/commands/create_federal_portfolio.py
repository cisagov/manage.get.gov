"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates a federal portfolio given a FederalAgency name"

    def add_arguments(self, parser):
        """Add three arguments:
        1. agency_name => the value of FederalAgency.agency
        2. --parse_requests => if true, adds the given portfolio to each related DomainRequest
        3. --parse_domains => if true, adds the given portfolio to each related DomainInformation
        """
        parser.add_argument(
            "agency_name",
            help="The name of the FederalAgency to add",
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

    def handle(self, agency_name, **options):
        parse_requests = options.get("parse_requests")
        parse_domains = options.get("parse_domains")
        both = options.get("both")

        if not both:
            if not parse_requests and not parse_domains:
                raise CommandError("You must specify at least one of --parse_requests or --parse_domains.")
        else:
            if parse_requests or parse_domains:
                raise CommandError("You cannot pass --parse_requests or --parse_domains when passing --both.")

        federal_agency = FederalAgency.objects.filter(agency__iexact=agency_name).first()
        if not federal_agency:
            raise ValueError(
                f"Cannot find the federal agency '{agency_name}' in our database. "
                "The value you enter for `agency_name` must be "
                "prepopulated in the FederalAgency table before proceeding."
            )

        portfolio = self.create_or_modify_portfolio(federal_agency)
        self.create_suborganizations(portfolio, federal_agency)

        if parse_requests or both:
            self.handle_portfolio_requests(portfolio, federal_agency)

        if parse_domains or both:
            self.handle_portfolio_domains(portfolio, federal_agency)

    def create_or_modify_portfolio(self, federal_agency):
        """Creates or modifies a portfolio record based on a federal agency."""
        portfolio_args = {
            "federal_agency": federal_agency,
            "organization_name": federal_agency.agency,
            "organization_type": DomainRequest.OrganizationChoices.FEDERAL,
            "creator": User.get_default_user(),
            "notes": "Auto-generated record",
        }

        if federal_agency.so_federal_agency.exists():
            portfolio_args["senior_official"] = federal_agency.so_federal_agency.first()

        portfolio, created = Portfolio.objects.get_or_create(
            organization_name=portfolio_args.get("organization_name"), defaults=portfolio_args
        )

        if created:
            message = f"Created portfolio '{portfolio}'"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

            if portfolio_args.get("senior_official"):
                message = f"Added senior official '{portfolio_args['senior_official']}'."
                TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
            else:
                message = (
                    "No senior official added. "
                    "None was returned for the reverse relation `FederalAgency.so_federal_agency.first()`."
                )
                TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
        else:
            proceed = TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=False,
                prompt_message=f"""
                The given portfolio '{federal_agency.agency}' already exists in our DB.
                If you cancel, the rest of the script will still execute but this record will not update.
                """,
                prompt_title="Do you wish to modify this record?",
            )
            if proceed:

                # Don't override the creator and notes fields
                if portfolio.creator:
                    portfolio_args.pop("creator")

                if portfolio.notes:
                    portfolio_args.pop("notes")

                # Update everything else
                for key, value in portfolio_args.items():
                    setattr(portfolio, key, value)

                portfolio.save()
                message = f"Modified portfolio '{portfolio}'"
                TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

                if portfolio_args.get("senior_official"):
                    message = f"Added/modified senior official '{portfolio_args['senior_official']}'."
                    TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

        return portfolio

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

        # Check if we need to update any existing suborgs first. This step is optional.
        existing_suborgs = Suborganization.objects.filter(name__in=org_names)
        if existing_suborgs.exists():
            self._update_existing_suborganizations(portfolio, existing_suborgs)

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

    def _update_existing_suborganizations(self, portfolio, orgs_to_update):
        """
        Update existing suborganizations with new portfolio.
        Prompts for user confirmation before proceeding.
        """
        proceed = TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=False,
            prompt_message=f"""Some suborganizations already exist in our DB.
            If you cancel, the rest of the script will still execute but these records will not update.

            ==Proposed Changes==
            The following suborgs will be updated: {[org.name for org in orgs_to_update]}
            """,
            prompt_title="Do you wish to modify existing suborganizations?",
        )
        if proceed:
            for org in orgs_to_update:
                org.portfolio = portfolio

            Suborganization.objects.bulk_update(orgs_to_update, ["portfolio"])
            message = f"Updated {len(orgs_to_update)} suborganizations."
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

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
        domain_requests = DomainRequest.objects.filter(federal_agency=federal_agency).exclude(status__in=invalid_states)
        if not domain_requests.exists():
            message = f"""
            Portfolios not added to domain requests: no valid records found.
            This means that a filter on DomainInformation for the federal_agency '{federal_agency}' returned no results.
            Excluded statuses: STARTED, INELIGIBLE, REJECTED.
            """
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return None

        # Get all suborg information and store it in a dict to avoid doing a db call
        suborgs = Suborganization.objects.filter(portfolio=portfolio).in_bulk(field_name="name")
        for domain_request in domain_requests:
            domain_request.portfolio = portfolio
            if domain_request.organization_name in suborgs:
                domain_request.sub_organization = suborgs.get(domain_request.organization_name)

        DomainRequest.objects.bulk_update(domain_requests, ["portfolio", "sub_organization"])
        message = f"Added portfolio '{portfolio}' to {len(domain_requests)} domain requests."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domains for a federal agency.
        Updates all relevant domain information records.
        """
        domain_infos = DomainInformation.objects.filter(federal_agency=federal_agency)
        if not domain_infos.exists():
            message = f"""
            Portfolios not added to domains: no valid records found.
            This means that a filter on DomainInformation for the federal_agency '{federal_agency}' returned no results.
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
        message = f"Added portfolio '{portfolio}' to {len(domain_infos)} domains"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
