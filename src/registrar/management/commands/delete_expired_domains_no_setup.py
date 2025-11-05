from django.core.management import BaseCommand
from registrar.models import Domain
import logging
import argparse
from django.utils import timezone
from datetime import timedelta
from ...utility.email_invitations import send_domain_deletion_emails_for_dns_needed_and_unknown_to_domain_managers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """If a domain is in the "Unknown" or "DNS Needed" state, and has been expired for 7 days,
    it is marked as deleted in the registrar, and in the registry."""

    def handle(self, *args, **options):
        domains_to_be_deleted = self.get_domains()
        dry_run = options.get("dry_run", False)

        if not dry_run:
            deleted_domains = self.delete_domains(domains_to_be_deleted)
            count = len(deleted_domains)
            plural = "s" if count > 1 else "" 
            logger.info(f'{count} domain{plural} have been deleted.')
            send_domain_deletion_emails_for_dns_needed_and_unknown_to_domain_managers(deleted_domains)
        else:
            logger.info(f'{len(domains_to_be_deleted)} will be deleted')
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            help="Show what would be changed without making any database modifications.",
        )
        return super().add_arguments(parser)

    def test_domains(self):
        domains = ["redwillowcountyne.gov", "servend.gov", "stanlycountync.gov"]
        domain_obj_list = []
        for domain in domains:
            obj,_ = Domain.objects.get_or_create(name=domain)
            domain_obj_list.append(obj)
            if obj.state == Domain.State.READY:
                obj.dns_needed()
        return domain_obj_list

    def get_domains(self):
        """Get domains that are dns needed or unknown"""
        # domain_state = [Domain.State.DNS_NEEDED, Domain.State.UNKNOWN]
        # domains = Domain.objects.filter(state__in=(domain_state), expiration_date__isnull=False).order_by("name")
        # time_to_compare = timezone.now().date() - timedelta(days=7)
        # domains_in_expired_state = list(filter (lambda d: d.expiration_date < time_to_compare, domains))
   
        # return domains_in_expired_state
        return self.test_domains()

    
    def delete_domains(self, domains):
        deleted_domains = []

        for domain in domains:
            if not domain.deletedInEpp():
                logger.info(f'{domain} was not deleted')
            else:
                deleted_domains.append(domain.name)
            domain.save()
        return deleted_domains
    
