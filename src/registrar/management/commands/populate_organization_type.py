import argparse
import logging
import os
from typing import List
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper, ScriptDataHelper
from registrar.models import DomainInformation, DomainRequest
from registrar.models.utility.generic_helper import CreateOrUpdateOrganizationTypeHelper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Loops through each valid DomainInformation and DomainRequest object and updates its organization_type value"

    def __init__(self):
        super().__init__()
        # Get lists for DomainRequest
        self.request_to_update: List[DomainRequest] = []
        self.request_failed_to_update: List[DomainRequest] = []
        self.request_skipped: List[DomainRequest] = []

        # Get lists for DomainInformation
        self.di_to_update: List[DomainInformation] = []
        self.di_failed_to_update: List[DomainInformation] = []
        self.di_skipped: List[DomainInformation] = []

        # Define a global variable for all domains with election offices
        self.domains_with_election_offices_set = set()

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)
        parser.add_argument(
            "domain_election_office_filename",
            help=("A JSON file that holds the location and filenames" "of all the data files used for migrations"),
        )

    def handle(self, domain_election_office_filename, **kwargs):
        """Loops through each valid Domain object and updates its first_created value"""
        debug = kwargs.get("debug")

        # Check if the provided file path is valid
        if not os.path.isfile(domain_election_office_filename):
            raise argparse.ArgumentTypeError(f"Invalid file path '{domain_election_office_filename}'")

        with open(domain_election_office_filename, "r") as file:
            for line in file:
                # Remove any leading/trailing whitespace
                domain = line.strip()
                if domain not in self.domains_with_election_offices_set:
                    self.domains_with_election_offices_set.add(domain)

        domain_requests = DomainRequest.objects.filter(
            organization_type__isnull=True, requested_domain__name__isnull=False
        )

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Proposed Changes==
            Number of DomainRequest objects to change: {len(domain_requests)}

            Organization_type data will be added for all of these fields.
            """,
            prompt_title="Do you wish to process DomainRequest?",
        )
        logger.info("Updating DomainRequest(s)...")

        self.update_domain_requests(domain_requests, debug)

        # We should actually be targeting all fields with no value for organization type,
        # but do have a value for generic_org_type. This is because there is data that we can infer.
        domain_infos = DomainInformation.objects.filter(organization_type__isnull=True)
        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Proposed Changes==
            Number of DomainInformation objects to change: {len(domain_infos)}

            Organization_type data will be added for all of these fields.
            """,
            prompt_title="Do you wish to process DomainInformation?",
        )
        logger.info("Updating DomainInformation(s)...")

        self.update_domain_informations(domain_infos, debug)

    def update_domain_requests(self, domain_requests, debug):
        for request in domain_requests:
            try:
                if request.generic_org_type is not None:
                    domain_name = request.requested_domain.name
                    request.is_election_board = domain_name in self.domains_with_election_offices_set
                    request = self.sync_organization_type(DomainRequest, request)
                    self.request_to_update.append(request)

                    if debug:
                        logger.info(f"Updating {request} => {request.organization_type}")
                else:
                    self.request_skipped.append(request)
                    if debug:
                        logger.warning(f"Skipped updating {request}. No generic_org_type was found.")
            except Exception as err:
                self.request_failed_to_update.append(request)
                logger.error(err)
                logger.error(f"{TerminalColors.FAIL}" f"Failed to update {request}" f"{TerminalColors.ENDC}")

        # Do a bulk update on the organization_type field
        ScriptDataHelper.bulk_update_fields(
            DomainRequest, self.request_to_update, ["organization_type", "is_election_board", "generic_org_type"]
        )

        # Log what happened
        log_header = "============= FINISHED UPDATE FOR DOMAINREQUEST ==============="
        TerminalHelper.log_script_run_summary(
            self.request_to_update, self.request_failed_to_update, self.request_skipped, debug, log_header
        )

    def update_domain_informations(self, domain_informations, debug):
        for info in domain_informations:
            try:
                if info.generic_org_type is not None:
                    domain_name = info.domain.name
                    info.is_election_board = domain_name in self.domains_with_election_offices_set
                    info = self.sync_organization_type(DomainInformation, info)
                    self.di_to_update.append(info)
                    if debug:
                        logger.info(f"Updating {info} => {info.organization_type}")
                else:
                    self.di_skipped.append(info)
                    if debug:
                        logger.warning(f"Skipped updating {info}. No generic_org_type was found.")
            except Exception as err:
                self.di_failed_to_update.append(info)
                logger.error(err)
                logger.error(f"{TerminalColors.FAIL}" f"Failed to update {info}" f"{TerminalColors.ENDC}")

        # Do a bulk update on the organization_type field
        ScriptDataHelper.bulk_update_fields(
            DomainInformation, self.di_to_update, ["organization_type", "is_election_board", "generic_org_type"]
        )

        # Log what happened
        log_header = "============= FINISHED UPDATE FOR DOMAININFORMATION ==============="
        TerminalHelper.log_script_run_summary(
            self.di_to_update, self.di_failed_to_update, self.di_skipped, debug, log_header
        )

    def sync_organization_type(self, sender, instance):
        """
        Updates the organization_type (without saving) to match
        the is_election_board and generic_organization_type fields.
        """

        # Define mappings between generic org and election org.
        # These have to be defined here, as you'd get a cyclical import error
        # otherwise.

        # For any given organization type, return the "_election" variant.
        # For example: STATE_OR_TERRITORY => STATE_OR_TERRITORY_ELECTION
        generic_org_map = DomainRequest.OrgChoicesElectionOffice.get_org_generic_to_org_election()

        # For any given "_election" variant, return the base org type.
        # For example: STATE_OR_TERRITORY_ELECTION => STATE_OR_TERRITORY
        election_org_map = DomainRequest.OrgChoicesElectionOffice.get_org_election_to_org_generic()

        # Manages the "organization_type" variable and keeps in sync with
        # "is_election_office" and "generic_organization_type"
        org_type_helper = CreateOrUpdateOrganizationTypeHelper(
            sender=sender,
            instance=instance,
            generic_org_to_org_map=generic_org_map,
            election_org_to_generic_org_map=election_org_map,
        )

        instance = org_type_helper.create_or_update_organization_type()
        return instance
