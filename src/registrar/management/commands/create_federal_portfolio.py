"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User, SeniorOfficial
from django.db.models import Q

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates a federal portfolio given a FederalAgency name"

    def add_arguments(self, parser):
        """Add our arguments."""
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

    def handle(self, agency_name, **options):
        parse_requests = options.get("parse_requests")
        parse_domains = options.get("parse_domains")

        if not parse_requests and not parse_domains:
            raise CommandError("You must specify at least one of --parse_requests or --parse_domains.")

        agencies = FederalAgency.objects.filter(agency__iexact=agency_name)

        # TODO - maybe we can add an option here to add this if it doesn't exist?
        if not agencies.exists():
            raise ValueError(
                f"Cannot find the federal agency '{agency_name}' in our database. "
                "The value you enter for `agency_name` must be "
                "prepopulated in the FederalAgency table before proceeding."
            )

        # There should be a one-to-one relationship between the name and the agency.
        federal_agency = agencies.get()

        portfolio = self.create_or_modify_portfolio(federal_agency)
        self.create_suborganizations(portfolio, federal_agency)

        if parse_requests:
            self.handle_portfolio_requests(portfolio, federal_agency)
        
        if parse_domains:
            self.handle_portfolio_domains(portfolio, federal_agency)

    def create_or_modify_portfolio(self, federal_agency):
        # TODO - state_territory, city, etc fields??? 
        portfolio_args = {
            "federal_agency": federal_agency,
            "organization_name": federal_agency.agency,
            "organization_type": DomainRequest.OrganizationChoices.FEDERAL,
            "creator": User.get_default_user(),
            "notes": "Auto-generated record",
        }

        senior_official = federal_agency.so_federal_agency
        if senior_official.exists():
            portfolio_args["senior_official"] = senior_official.first()

        # Create the Portfolio value if it doesn't exist
        existing_portfolio = Portfolio.objects.filter(organization_name=federal_agency.agency)
        if not existing_portfolio.exists():
            portfolio = Portfolio.objects.create(**portfolio_args)
            message = f"Created portfolio '{federal_agency.agency}'"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
            return portfolio
        else:
            if len(existing_portfolio) > 1:
                raise ValueError(f"Could not update portfolio '{federal_agency.agency}': multiple records exist.")

            # TODO a dialog to confirm / deny doing this
            existing_portfolio.update(**portfolio_args)
            message = f"Modified portfolio '{federal_agency.agency}'"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
            return existing_portfolio

    def create_suborganizations(self, portfolio: Portfolio, federal_agency: FederalAgency):
        non_federal_agency = FederalAgency.objects.get(agency="Non-Federal Agency")
        valid_agencies = DomainInformation.objects.filter(federal_agency=federal_agency).exclude(
            Q(federal_agency=non_federal_agency) | Q(federal_agency__isnull=True)
        )

        org_names = valid_agencies.values_list("organization_name", flat=True)
        if len(org_names) < 1:
            message =f"No suborganizations found for {federal_agency.agency}"
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, message)
            return

        # Check if we need to update any existing suborgs first.
        # This step is optional.
        existing_suborgs = Suborganization.objects.filter(name__in=org_names)
        if len(existing_suborgs) > 1:
            # TODO - we need a prompt here if any are found
            for org in existing_suborgs:
                org.portfolio = portfolio

            Suborganization.objects.bulk_update(existing_suborgs, ["portfolio"])
            message = f"Updated {len(existing_suborgs)} suborganizations"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

        # Add any suborgs that don't presently exist
        suborgs = []
        for name in org_names:
            if name not in existing_suborgs:
                suborg = Suborganization(
                    name=name,
                    portfolio=portfolio,
                )
                suborgs.append(suborg)

        Suborganization.objects.bulk_create(suborgs)

        message = f"Added {len(org_names)} suborganizations..."
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_requests(self, portfolio: Portfolio, federal_agency: FederalAgency):
        domain_requests = DomainInformation.objects.filter(federal_agency=federal_agency)
        if len(domain_requests) < 1:
            message = f"Portfolios not added to domain requests: no valid records found"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return

        for domain_request in domain_requests:
            domain_request.portfolio = portfolio
        
        DomainRequest.objects.bulk_update(domain_requests, ["portfolio"])
        message = f"Added portfolio to {len(domain_requests)} domain requests"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        domain_infos = DomainInformation.objects.filter(federal_agency=federal_agency)

        if len(domain_infos) < 1:
            message = f"Portfolios not added to domains: no valid records found"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return

        for domain_info in domain_infos:
            domain_info.portfolio = portfolio

        DomainInformation.objects.bulk_update(domain_infos, ["portfolio"])

        message = f"Added portfolio to {len(domain_infos)} domains"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
