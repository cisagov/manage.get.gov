from django.core.management import BaseCommand
from registrar.models import Domain, UserDomainRole
import logging
import argparse
from django.utils import timezone
from datetime import timedelta
from registrar.utility.email import EmailSendingError, send_templated_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """If a domain is in the "Unknown" or "DNS Needed" state, and has been expired for 7 days,
    it is marked as deleted in the registrar, and in the registry."""

    def handle(self, *args, **options):
        domains_to_be_deleted = self.get_domains()
        dry_run = options.get("dry_run", False)

        if not dry_run:
            deleted_domains = self.delete_domains_and_send_notif_emails(domains_to_be_deleted)
            self.logging_message(dry_run, deleted_domains)
        else:
            self.logging_message(dry_run, domains_to_be_deleted)

    def logging_message(self, dry_run, domains):
        count = len(domains)
        if dry_run:
            logger.info(f"{count} domain will be deleted")
        else:
            if count > 1:
                logger.info(f"{count} domains have been deleted.")
            else:
                text = "No" if count == 0 else "1"
                logger.info(f"{text} domain has been deleted.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            help="Show what would be changed without making any database modifications.",
        )
        return super().add_arguments(parser)

    def get_domains(self):
        """Get domains that are dns needed or unknown"""
        domain_state = [Domain.State.DNS_NEEDED, Domain.State.UNKNOWN]
        domains = Domain.objects.filter(state__in=(domain_state), expiration_date__isnull=False)
        time_to_compare = (timezone.now() - timedelta(days=7)).date()

        domains_in_expired_state = list(filter(lambda d: d.expiration_date == time_to_compare, domains))
        return domains_in_expired_state

    def delete_domains_and_send_notif_emails(self, domains):
        deleted_domains = []
        for domain in domains:
            try:
                domain.deletedInEpp()
                domain.save()
                deleted_domains.append(domain)
            except Exception:
                logger.error(f"An error occured with {domain.name}")

        if len(deleted_domains) > 0:
            self.send_domain_notifications_emails(deleted_domains)
        return deleted_domains

    def send_domain_notifications_emails(self, domains):
        """Send email to domain managers that the domain has been deleted"""
        all_emails_sent = True
        subject_txt = "emails/domain_deletion_dns_needed_unknown_subject.txt"
        body_txt = "emails/domain_deletion_dns_needed_unknown_body.txt"
        for domain in domains:
            user_domain_roles_emails = list(
                UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct()
            )

            try:
                send_templated_email(
                    template_name=body_txt,
                    subject_template_name=subject_txt,
                    to_addresses=user_domain_roles_emails,
                    context={"domain": domain, "date_of_deletion": domain.deleted.date()},
                )
            except EmailSendingError as err:
                logger.error(
                    "Failed to send domain deletion domain manager emails"
                    f"Subject template: domain_deletion_dns_needed_unknown_subject.txt"
                    f"To: {user_domain_roles_emails}"
                    f"Domain: {domain.name}"
                    f"Error: {err}"
                )
                all_emails_sent = False

            if all_emails_sent:
                logger.info("Emails sent out successfully")
            else:
                logger.error("Some domain expiration emails failed to send.")
        return all_emails_sent
