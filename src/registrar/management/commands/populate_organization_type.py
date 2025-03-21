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
    help = (
        "Loops through each valid DomainInformation and DomainRequest object and updates its organization_type value. "
        "A valid DomainInformation/DomainRequest in this sense is one that has the value None for organization_type. "
        "In other words, we populate the organization_type field if it is not already populated."
    )

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
        self.domains_with_election_boards_set = set()

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument(
            "domain_election_board_filename",
            help=("A file that contains" " all the domains that are election offices."),
        )

    def handle(self, domain_election_board_filename, **kwargs):
        """Loops through each valid Domain object and updates its first_created value"""

        # Check if the provided file path is valid
        if not os.path.isfile(domain_election_board_filename):
            raise argparse.ArgumentTypeError(f"Invalid file path '{domain_election_board_filename}'")

        # Read the election office csv
        self.read_election_board_file(domain_election_board_filename)

        domain_requests = DomainRequest.objects.filter(organization_type__isnull=True)

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            ==Proposed Changes==
            Number of DomainRequest objects to change: {len(domain_requests)}

            Organization_type data will be added for all of these fields.
            """,
            prompt_title="Do you wish to process DomainRequest?",
        )
        logger.info("Updating DomainRequest(s)...")

        self.update_domain_requests(domain_requests)

        # We should actually be targeting all fields with no value for organization type,
        # but do have a value for generic_org_type. This is because there is data that we can infer.
        domain_infos = DomainInformation.objects.filter(organization_type__isnull=True)
        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            ==Proposed Changes==
            Number of DomainInformation objects to change: {len(domain_infos)}

            Organization_type data will be added for all of these fields.
            """,
            prompt_title="Do you wish to process DomainInformation?",
        )
        logger.info("Updating DomainInformation(s)...")

        self.update_domain_informations(domain_infos)

    def read_election_board_file(self, domain_election_board_filename):
        """
        Reads the election board file and adds each parsed domain to self.domains_with_election_boards_set.
        As previously implied, this file contains information about Domains which have election boards.

        The file must adhere to this format:
        ```
        domain1.gov
        domain2.gov
        domain3.gov
        ```
        (and so on)
        """
        with open(domain_election_board_filename, "r") as file:
            for line in file:
                # Remove any leading/trailing whitespace
                domain = line.strip()
                if domain not in self.domains_with_election_boards_set:
                    self.domains_with_election_boards_set.add(domain)

    def update_domain_requests(self, domain_requests):
        """
        Updates the organization_type for a list of DomainRequest objects using the `sync_organization_type` function.
        Results are then logged.

        This function updates the following variables:
        - self.request_to_update list is appended to if the field was updated successfully.
        - self.request_skipped list is appended to if the field has `None` for `request.generic_org_type`.
        - self.request_failed_to_update list is appended to if an exception is caught during update.
        """
        for request in domain_requests:
            try:
                if request.generic_org_type is not None:
                    domain_name = None
                    if request.requested_domain is not None and request.requested_domain.name is not None:
                        domain_name = request.requested_domain.name

                    request_is_approved = request.status == DomainRequest.DomainRequestStatus.APPROVED
                    if request_is_approved and domain_name is not None and not request.is_election_board:
                        request.is_election_board = domain_name in self.domains_with_election_boards_set

                    self.sync_organization_type(DomainRequest, request)
                    self.request_to_update.append(request)
                    logger.info(f"Updating {request} => {request.organization_type}")
                else:
                    self.request_skipped.append(request)
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
            self.request_to_update,
            self.request_failed_to_update,
            self.request_skipped,
            [],
            debug=True,
            log_header=log_header,
        )

        update_skipped_count = len(self.request_to_update)
        if update_skipped_count > 0:
            logger.warning(
                f"""{TerminalColors.MAGENTA}
                Note: Entries are skipped when generic_org_type is None
                {TerminalColors.ENDC}
                """
            )

    def update_domain_informations(self, domain_informations):
        """
        Updates the organization_type for a list of DomainInformation objects
        and updates is_election_board if the domain is in the provided csv.
        Results are then logged.

        This function updates the following variables:
        - self.di_to_update list is appended to if the field was updated successfully.
        - self.di_skipped list is appended to if the field has `None` for `request.generic_org_type`.
        - self.di_failed_to_update list is appended to if an exception is caught during update.
        """
        for info in domain_informations:
            try:
                if info.generic_org_type is not None:
                    domain_name = info.domain.name

                    if not info.is_election_board:
                        info.is_election_board = domain_name in self.domains_with_election_boards_set

                    self.sync_organization_type(DomainInformation, info)

                    self.di_to_update.append(info)
                    logger.info(f"Updating {info} => {info.organization_type}")
                else:
                    self.di_skipped.append(info)
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
            self.di_to_update, self.di_failed_to_update, self.di_skipped, [], debug=True, log_header=log_header
        )

        update_skipped_count = len(self.di_skipped)
        if update_skipped_count > 0:
            logger.warning(
                f"""{TerminalColors.MAGENTA}
                Note: Entries are skipped when generic_org_type is None
                {TerminalColors.ENDC}
                """
            )

    def sync_organization_type(self, sender, instance):
        """
        Updates the organization_type (without saving) to match
        the is_election_board and generic_organization_type fields.
        """

        # Define mappings between generic org and election org.
        # These have to be defined here, as you'd get a cyclical import error
        # otherwise.

        # For any given organization type, return the "_ELECTION" enum equivalent.
        # For example: STATE_OR_TERRITORY => STATE_OR_TERRITORY_ELECTION
        generic_org_map = DomainRequest.OrgChoicesElectionOffice.get_org_generic_to_org_election()

        # For any given "_election" variant, return the base org type.
        # For example: STATE_OR_TERRITORY_ELECTION => STATE_OR_TERRITORY
        election_org_map = DomainRequest.OrgChoicesElectionOffice.get_org_election_to_org_generic()

        # Manages the "organization_type" variable and keeps in sync with
        # "is_election_board" and "generic_organization_type"
        org_type_helper = CreateOrUpdateOrganizationTypeHelper(
            sender=sender,
            instance=instance,
            generic_org_to_org_map=generic_org_map,
            election_org_to_generic_org_map=election_org_map,
        )

        org_type_helper.create_or_update_organization_type(force_update=True)
