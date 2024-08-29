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
        """Tries to create a portfolio record based off of a federal agency.
        If the record already exists, we prompt the user to proceed then
        update the record."""
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
            message = f"Created portfolio '{portfolio}'"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
            return portfolio
        else:

            proceed = TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=False,
                info_to_inspect=f"""The given portfolio '{federal_agency.agency}' already exists in our DB.
                If you cancel, the rest of the script will still execute but this record will not update.
                """,
                prompt_title="Do you wish to modify this record?",
            )
            if not proceed:
                if len(existing_portfolio) > 1:
                    raise ValueError(f"Could not use portfolio '{federal_agency.agency}': multiple records exist.")
                else:
                    # Just return the portfolio object without modifying it
                    return existing_portfolio.get()

            if len(existing_portfolio) > 1:
                raise ValueError(f"Could not update portfolio '{federal_agency.agency}': multiple records exist.")

            existing_portfolio.update(**portfolio_args)
            message = f"Modified portfolio '{existing_portfolio.first()}'"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)
            return existing_portfolio.get()

    def create_suborganizations(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """Given a list of organization_names on DomainInformation objects (filtered by agency),
        create multiple Suborganizations tied to the given portfolio"""
        valid_agencies = DomainInformation.objects.filter(federal_agency=federal_agency)
        org_names = valid_agencies.values_list("organization_name", flat=True)
        if len(org_names) < 1:
            message = f"No suborganizations found for {federal_agency}"
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, message)
            return

        # Check if we need to update any existing suborgs first.
        # This step is optional.
        existing_suborgs = Suborganization.objects.filter(name__in=org_names)
        if len(existing_suborgs) > 0:
            self._update_existing_suborganizations(portfolio, existing_suborgs)

        # Add any suborgs that don't presently exist
        excluded_org_names = existing_suborgs.values_list("name", flat=True)
        suborgs = []
        for name in org_names:
            if name and name not in excluded_org_names:
                if portfolio.organization_name and name.lower() == portfolio.organization_name.lower():
                    # If the suborg name is the name that currently exists,
                    # thats not a suborg - thats the portfolio itself!
                    # In this case, we can use this as an opportunity to update
                    # address information and the like
                    self._update_portfolio_location_details(portfolio, valid_agencies.get(organization_name=name))
                else:
                    suborg = Suborganization(
                        name=name,
                        portfolio=portfolio,
                    )
                    suborgs.append(suborg)

        if len(org_names) > 1:
            Suborganization.objects.bulk_create(suborgs)
            message = f"Added {len(suborgs)} suborganizations"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
        else:
            message = "No suborganizations added"
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, message)

    def _update_existing_suborganizations(self, portfolio, orgs_to_update):
        proceed = TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=False,
            info_to_inspect=f"""Some suborganizations already exist in our DB.
            If you cancel, the rest of the script will still execute but these records will not update.

            ==Proposed Changes==
            The following suborgs will be updated: {[org.name for org in orgs_to_update]}
            """,
            prompt_title="Do you wish to modify existing suborganizations?",
        )
        if not proceed:
            return

        for org in orgs_to_update:
            org.portfolio = portfolio

        Suborganization.objects.bulk_update(orgs_to_update, ["portfolio"])
        message = f"Updated {len(orgs_to_update)} suborganizations"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

    def _update_portfolio_location_details(self, portfolio: Portfolio, domain_info: DomainInformation):
        """Adds location information to the given portfolio based off of the values in
        DomainInformation"""
        location_props = [
            "address_line1",
            "address_line2",
            "city",
            "state_territory",
            "zipcode",
            "urbanization",
        ]

        for prop_name in location_props:
            # Copy the value from the domain info object to the portfolio object
            value = getattr(domain_info, prop_name)
            setattr(portfolio, prop_name, value)
        portfolio.save()

        message = f"Updated location details on portfolio '{portfolio}'"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_requests(self, portfolio: Portfolio, federal_agency: FederalAgency):
        domain_requests = DomainInformation.objects.filter(federal_agency=federal_agency)
        if len(domain_requests) < 1:
            message = "Portfolios not added to domain requests: no valid records found"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return

        for domain_request in domain_requests:
            domain_request.portfolio = portfolio

        DomainRequest.objects.bulk_update(domain_requests, ["portfolio"])
        message = f"Added portfolio '{portfolio}' to {len(domain_requests)} domain requests"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        domain_infos = DomainInformation.objects.filter(federal_agency=federal_agency)

        if len(domain_infos) < 1:
            message = "Portfolios not added to domains: no valid records found"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
            return

        for domain_info in domain_infos:
            domain_info.portfolio = portfolio

        DomainInformation.objects.bulk_update(domain_infos, ["portfolio"])

        message = f"Added portfolio '{portfolio}' to {len(domain_infos)} domains"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
