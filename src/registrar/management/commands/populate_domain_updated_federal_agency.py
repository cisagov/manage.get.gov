""""
TODO: write description
"""

import logging
import copy

from django.core.management import BaseCommand
from registrar.models import DomainInformation, DomainRequest, FederalAgency
from registrar.management.commands.utility.terminal_helper import ScriptDataHelper


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Transfers Domain Request and Domain Information federal agency field from string to FederalAgency object"

    # Deprecated federal agency names mapped to designated replacements
    rename_deprecated_federal_agency = {
        "Appraisal Subcommittee": "Appraisal Subcommittee of the Federal Financial Institutions Examination Council",
        "Barry Goldwater Scholarship and Excellence in Education Program": "Barry Goldwater Scholarship and Excellence in Education Foundation",
        "Federal Reserve System": "Federal Reserve Board of Governors",
        "Harry S Truman Scholarship Foundation": "Harry S. Truman Scholarship Foundation",
        "Japan-US Friendship Commission": "Japan-U.S. Friendship Commission",
        "Japan-United States Friendship Commission": "Japan-U.S. Friendship Commission",
        "John F. Kennedy Center for Performing Arts": "John F. Kennedy Center for the Performing Arts",
        "Occupational Safety & Health Review Commission": "Occupational Safety and Health Review Commission",
        "Corporation for National & Community Service": "Corporation for National and Community Service",
        "Export/Import Bank of the U.S.": "Export-Import Bank of the United States",
        "Medical Payment Advisory Commission": "Medicare Payment Advisory Commission",
        "U.S. Peace Corps": "Peace Corps",
        "Chemical Safety Board": "U.S. Chemical Safety Board",
        "Nuclear Waste Technical Review Board": "U.S. Nuclear Waste Technical Review Board",
        "State, Local, and Tribal Government": "Non-Federal Agency",
    }

    def find_federal_agency_row(self, domain_object):
        federal_agency = domain_object.federal_agency
        # Domain Information objects without a federal agency default to Non-Federal Agency
        if federal_agency is None:
            federal_agency = "Non-Federal Agency"
        if federal_agency in self.rename_deprecated_federal_agency.keys():
            federal_agency = self.rename_deprecated_federal_agency[federal_agency]
        return FederalAgency.objects.filter(agency=federal_agency).get()

    def handle(self, **options):
        """
        Converts all ready and DNS needed domains with a non-default public contact
        to disclose their public contact.
        """
        logger.info("Transferring federal agencies to FederalAgency object")
        # DomainInforation object we populate with updated_federal_agency which are then bulk updated
        domain_infos_to_update = []
        domain_requests_to_update = []
        # domain requests with null federal_agency that are not populated with updated_federal_agency
        domain_requests_skipped = []
        domain_infos_with_errors = []
        domain_requests_with_errors = []

        # Initializes domain request and domain info objects that need to update federal agency
        # filter out domains with federal agency null or Non-Federal Agency
        domain_infos = DomainInformation.objects.all()
        domain_requests = DomainRequest.objects.all()

        logger.info(f"Found {len(domain_infos)} DomainInfo objects with federal agency.")

        for domain_info in domain_infos:
            try:
                federal_agency_row = self.find_federal_agency_row(domain_info)
                domain_info.updated_federal_agency = federal_agency_row
                domain_infos_to_update.append(domain_info)
                logger.info(
                    f"DomainInformation {domain_info} updated_federal_agency set to: {domain_info.updated_federal_agency}"
                )
            except Exception as err:
                logger.info(
                    f"DomainInformation for {domain_information} failed to update updated_federal_agency: {err}"
                )
                domain_infos_with_errors.append(domain_info)

        ScriptDataHelper.bulk_update_fields(DomainInformation, domain_infos_to_update, ["updated_federal_agency"])

        for domain_request in domain_requests:
            try:
                if domain_request.federal_agency is None:
                    domain_requests_skipped.append(domain_request)
                else:
                    federal_agency_row = self.find_federal_agency_row(domain_request)
                    domain_request.updated_federal_agency = federal_agency_row
                    domain_requests_to_update.append(domain_request)
                    logger.info(
                        f"DomainRequest {domain_request} updated_federal_agency set to: {domain_request.updated_federal_agency}"
                    )
            except Exception as err:
                logger.info(f"DomainRequest for {domain_request} failed to update updated_federal_agency: {err}")
                domain_requests_with_errors.append(domain_request)

        ScriptDataHelper.bulk_update_fields(DomainRequest, domain_requests_to_update, ["updated_federal_agency"])

        logger.info(f"{len(domain_infos_to_update)} DomainInformation rows updated update_federal_agency.")
        logger.info(
            f"{len(domain_infos_with_errors)} DomainInformation rows errored when updating update_federal_agency."
        )
        logger.info(f"{len(domain_requests_to_update)} DomainRequest rows updated update_federal_agency.")
        logger.info(f"{len(domain_requests_skipped)} DomainRequest rows with null federal_agency skipped.")
        logger.info(
            f"{len(domain_requests_with_errors)} DomainRequest rows errored when updating update_federal_agency.\n{domain_requests_with_errors}"
        )
