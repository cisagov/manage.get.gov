""""
Converts all ready and DNS needed domains with a non-default public contact
to disclose their public contact. Created for Issue#1535 to resolve
 disclose issue of domains with missing security emails.
"""

import logging
import copy

from django.core.management import BaseCommand
from registrar.models import Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Disclose all nondefault domain security emails."

    def __init__(self):
        """Sets global variables for code tidyness"""
        super().__init__()
        # domains and transition domains that must be disclosed to true
        self.contacts_saved_count = 0
        # domains with errors, which are not successfully updated to disclose
        self.domains_with_errors: list[str] = []
        # domains that are successfully disclosed
        self.disclosed_domain_contacts_count = 0
        # domains that skip disclose due to having contact registrar@dotgov.gov
        self.skipped_domain_contacts_count = 0

    def handle(self, **options):
        """
        Converts all ready and DNS needed domains with a non-default public contact
        to disclose their public contact.
        """
        logger.info("Updating security emails to public")

        # Initializes domains that need to be disclosed

        statuses = [Domain.State.READY, Domain.State.DNS_NEEDED]
        domains = Domain.objects.filter(state__in=statuses)

        logger.info(f"Found {len(domains)} domains with status Ready or DNS Needed.")

        # Call security_contact on all domains to trigger saving contact information
        for domain in domains:
            contact = domain.security_contact
            self.contacts_saved_count+=1

        logger.info(f"Found {self.contacts_saved_count} security contacts.")

        # Update EPP contact for domains with a security contact
        for domain in domains:
            try:
                logger.info(
                    f"Domain {domain.domain_info} security contact: {domain.security_contact.email}"
                )
                if domain.security_contact.email != "registrar@dotgov.gov":
                    domain._update_epp_contact(contact=domain.security_contact)
                    self.disclosed_domain_contacts_count+=1
                else:
                    logger.info(
                        f"Skipping disclose for {domain.domain_info} security contact {domain.security_contact.email}."
                    )
                    self.skipped_domain_contacts_count+=1
            except Exception as err:
                # error condition if domain not in database
                self.domains_with_errors.append(copy.deepcopy(domain.domain_info))
                logger.error(
                    f"error retrieving domain {domain.domain_info} contact {domain.security_contact}: {err}"
                )

        # Inform user how many contacts were disclosed, skipped, and errored
        logger.info(f"Updated {self.disclosed_domain_contacts_count} contacts to disclosed.")
        logger.info(
            f"Skipped disclosing {self.skipped_domain_contacts_count} contacts with security email registrar@dotgov.gov."            
        )
        logger.info(
            f"Error disclosing the following {len(self.domains_with_errors)} contacts: {self.domains_with_errors}"
        )