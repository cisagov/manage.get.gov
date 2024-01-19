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
        """Sets global variables for code tidiness"""
        super().__init__()
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

        # Update EPP contact for domains with a security contact
        for domain in domains:
            try:
                contact = domain.security_contact  # noqa on these items as we only want to call security_contact
                logger.info(f"Domain {domain.name} security contact: {domain.security_contact.email}")
                if domain.security_contact.email != "registrar@dotgov.gov":
                    domain._update_epp_contact(contact=domain.security_contact)
                    self.disclosed_domain_contacts_count += 1
                else:
                    logger.info(
                        f"Skipping disclose for {domain.name} security contact {domain.security_contact.email}."
                    )
                    self.skipped_domain_contacts_count += 1
            except Exception as err:
                # error condition if domain not in database
                self.domains_with_errors.append(copy.deepcopy(domain.name))
                logger.error(f"error retrieving domain {domain.name} contact {domain.security_contact}: {err}")

        # Inform user how many contacts were disclosed, skipped, and errored
        logger.info(f"Updated {self.disclosed_domain_contacts_count} contacts to disclosed.")
        logger.info(
            f"Skipped disclosing {self.skipped_domain_contacts_count} contacts with security email "
            f"registrar@dotgov.gov."
        )
        logger.info(
            f"Error disclosing the following {len(self.domains_with_errors)} contacts: {self.domains_with_errors}"
        )
