""""Script description"""

import logging
import copy

from django.core.management import BaseCommand
from registrar.models import Domain

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    # TODO: write script description here
    help = "Description"

    def __init__(self):
        """Sets global variables for code tidyness"""
        super().__init__()
        # domains and transition domains that must be disclosed to true
        self.domains_to_disclose: List[str] = []
        # domains with errors, which are not successfully updated to disclose
        self.domains_with_errors: List[str] = []
        # domains that are successfully disclosed
        self.disclosed_domain_contacts: List[str] = []
        # domains that skip disclose due to having contact registrar@dotgov.gov
        self.skipped_domain_contacts: List[str] = []

    def handle(self, **options):
        """
        Description for what update_security_email_disclose does
        """
        logger.info("Updating security emails to public")
        
        # Initializes domains that need to be disclosed
        statuses=["ready", "dns needed"]
        domains = Domain.objects.filter(
            state__in=statuses
        )
        
        # Call security_contact on all domains to trigger saving contact information
        for domain in domains:
            contact = domain.security_contact

        logger.info("Found %d domains with status Ready or DNS Needed.", len(domains))

        # Update EPP contact for domains with a security contact
        for domain in domains:
            try:
                logger.info("Domain %s security contact: %s", domain.domain_info, domain.security_contact.email)
                if domain.security_contact.email != "registrar@dotgov.gov":
                    domain._update_epp_contact(contact=domain.security_contact)
                    self.disclosed_domain_contacts.append(copy.deepcopy(domain.security_contact))
                else:
                    logger.info("Skipping disclose for %s security contact %s.", 
                    domain.domain_info, domain.security_contact.email)
                    self.skipped_domain_contacts.append(copy.deepcopy(domain.security_contact))
            except Exception as err:
                # error condition if domain not in database
                self.domains_with_errors.append(copy.deepcopy(domain.domain_info))
                logger.error(f"error retrieving domain {domain.domain_info}: {err}")

        # Inform user how many contacts were disclosed and skipped
        logger.info("Updated %d contacts to disclosed.", len(self.disclosed_domain_contacts))
        logger.info("Skipped disclosing %d contacts with security email registrar@dotgov.gov.", 
        len(self.skipped_domain_contacts))
        
        
