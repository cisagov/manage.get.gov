import argparse
import logging
from typing import List
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper, ScriptDataHelper
from registrar.models import DomainInformation, DomainRequest, Domain

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

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)
        parser.add_argument(
            "election_office_filename",
            help=("A JSON file that holds the location and filenames" "of all the data files used for migrations"),
        )

    def handle(self, **kwargs):
        """Loops through each valid Domain object and updates its first_created value"""
        debug = kwargs.get("debug")
        domain_requests = DomainRequest.objects.filter(organization_type__isnull=True)

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

        domain_infos = DomainInformation.objects.filter(domain_request__isnull=False, organization_type__isnull=True)
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
                # TODO - parse data from hfile ere
                if request.generic_org_type is not None:
                    request.is_election_board = True
                    self.request_to_update.append(request)
                    if debug:
                        logger.info(f"Updating {request}")
                else:
                    self.request_skipped.append(request)
                    if debug:
                        logger.warning(f"Skipped updating {request}")
            except Exception as err:
                self.request_failed_to_update.append(request)
                logger.error(err)
                logger.error(f"{TerminalColors.FAIL}" f"Failed to update {request}" f"{TerminalColors.ENDC}")

        # Do a bulk update on the organization_type field
        ScriptDataHelper.bulk_update_fields(DomainRequest, self.request_to_update, ["organization_type"])

        # Log what happened
        log_header = "============= FINISHED UPDATE FOR DOMAINREQUEST ==============="
        TerminalHelper.log_script_run_summary(
            self.request_to_update, self.request_failed_to_update, self.request_skipped, debug, log_header
        )
    
    def update_domain_informations(self, domain_informations, debug):
        for info in domain_informations:
            try:
                # TODO - parse data from hfile ere
                if info.generic_org_type is not None:
                    info.is_election_board = True
                    self.di_to_update.append(info)
                    if debug:
                        logger.info(f"Updating {info}")
                else:
                    self.di_skipped.append(info)
                    if debug:
                        logger.warning(f"Skipped updating {info}")
            except Exception as err:
                self.di_failed_to_update.append(info)
                logger.error(err)
                logger.error(f"{TerminalColors.FAIL}" f"Failed to update {info}" f"{TerminalColors.ENDC}")

        # Do a bulk update on the organization_type field
        ScriptDataHelper.bulk_update_fields(DomainInformation, self.di_to_update, ["organization_type"])

        # Log what happened
        log_header = "============= FINISHED UPDATE FOR DOMAININFORMATION ==============="
        TerminalHelper.log_script_run_summary(
            self.di_to_update, self.di_failed_to_update, self.di_skipped, debug, log_header
        )

