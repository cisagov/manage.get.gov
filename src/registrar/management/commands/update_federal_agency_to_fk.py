""""
TODO: write description
"""

import logging
import copy

from django.core.management import BaseCommand
from registrar.models import DomainInformation, DomainRequest, FederalAgency

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Transfers Domain Request and Domain Information federal agency field from string to FederalAgency fk"

    def __init__(self):
        """Sets global variables for code tidiness"""
        super().__init__()
        # domains with errors, which do not successfully update federal agency to FederalAgency fk
        self.domains_with_errors: list[str] = []
        # domains that successfull update federal agency to FederalAgency fk
        self.domains_successfully_updated = 0

    def handle(self, **options):
        """
        Converts all ready and DNS needed domains with a non-default public contact
        to disclose their public contact.
        """
        logger.info("Transferring federal agencies to FederalAgency foreign key")
        
        # Initializes domain request and domain info objects that need to update federal agency
        # filter out domains with federal agency null or Non-Federal Agency
        domain_infos = DomainInformation.objects.filter(
            federal_agency__isnull=False
        ).exclude(
            federal_agency="Non-Federal Agency"
        )

        logger.info(f"Found {len(domain_infos)} DomainInfo objects with federal agency.")

        # Update EPP contact for domains with a security contact
        for domain in domain_infos:
            # try:
            federal_agency = domain.federal_agency  # noqa on these items as we only want to call security_contact
            logger.info(f"Domain {domain} federal agency: {federal_agency}")
        #     except Exception as err:
        #         # error condition if domain not in database
        #         self.domains_with_errors.append(copy.deepcopy(domain.name))
        #         logger.error(f"error retrieving domain {domain.name} contact {domain.security_contact}: {err}")

        # # Inform user how many contacts were disclosed, skipped, and errored
        # logger.info(f"Updated {self.disclosed_domain_contacts_count} contacts to disclosed.")
        # logger.info(
        #     f"Error disclosing the following {len(self.domains_with_errors)} contacts: {self.domains_with_errors}"
        # )
