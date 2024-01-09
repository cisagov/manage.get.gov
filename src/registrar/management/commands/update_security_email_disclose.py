""""Script description"""

import logging

from django.core.management import BaseCommand
from registrar.models import Domain

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    # TODO: write script description here
    help = "Description"

    def __init__(self):
        """Sets global variables for code tidyness"""
        super().__init__()
        # this array is used to store domains with errors, which are not
        # successfully updated to disclose
        domains_with_errors: List[str] = []

    def handle(self, **options):
        """
        Description for what update_security_email_disclose does
        """
        logger.info("Updating security emails to public")

        domains = Domain.objects.filter()
        
        # Call security_contact on all domains to trigger saving contact information
        for domain in domains:
            contact = domain.security_contact

        domains_with_contact = Domain.objects.filter(
            security_contact_registry_id=True
        )
        logger.info("Found %d domains with security contact.", len(domains_with_contact))

        # Update EPP contact for domains with a security contact
        for domain in domains_with_contact:
            try:
                domain._update_epp_contact(contact=domain.security_contact_registry_id)
                logger.info("Updated EPP contact for domain %d to disclose: %d", domain, domain.security_contact.disclose)
            except Exception as err:
                # error condition if domain not in database
                self.domains_with_errors.append(copy.deepcopy(domain.domain_name))
                logger.error(f"error retrieving domain {domain.domain_name}: {err}")

        domains_disclosed = Domain.objects.filter(
            security_contact_registry_id=True,
        )
        logger.info("Updated %d domains to disclosed.", len(domains_disclosed))
        
        
