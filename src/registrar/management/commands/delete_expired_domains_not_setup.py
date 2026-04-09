from datetime import timedelta
from django.core.management import BaseCommand
from registrar.models import Domain, UserDomainRole
import logging
import argparse
from django.utils import timezone
from registrar.utility.email import EmailSendingError, send_templated_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Domains that, (1) have DNS status "Unknown" or "DNS Needed" and (2) are 7+ days past their expiration date,
    are marked "DELETED" in the registrar and deleted in the registry."""

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
            logger.info(f"DRY RUN MODE - No changes will be made\n {count} domains will be deleted if not in dry run mode: {domains}")
        else:
            if count > 1:
                logger.info(f"{count} domains have been deleted: {domains}")
            else:
                text = "No" if count == 0 else "1"
                logger.info(f"{text} domain has been deleted. {domains}")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action=argparse.BooleanOptionalAction,
            help="Show what would be changed without making any database modifications.",
        )
        return super().add_arguments(parser)

    def get_domains(self):
        """Get domains with DNS status DNS needed or Unknown
        whose expiration date is equal to the current date.
        If the domain has a null expiration date, creation date + 1yr is used
        as a default expiration date instead.
        We check for null expiration dates because expiration is not currently
        applied to domains in UNKNOWN state. We do not expect it to be null
        for any other domain state."""
        today_date = timezone.now().date()

        domains_in_expired_state = Domain.objects.filter(
            state__in=[Domain.State.DNS_NEEDED, Domain.State.UNKNOWN],
        ).filter(
            Q(expiration_date=today_date) | Q(expiration_date__isnull=True)
        ).order_by("id")

        for domain in domains_in_expired_state:
            if domain.expiration_date is None:
                logger.warning(
                    "Domain %s (id: %s) has a null expiration date in state %s. "
                    "Using creation date + 30 days as default expiration instead.",
                    domain.name,
                    domain.id,
                    domain.state,
                )
                default_expiration = domain.creation_date + timedelta(days=365)
                if default_expiration != today_date:
                    domains_in_expired_state = domains_in_expired_state.exclude(id=domain.id)

        return domains_in_expired_state

    def delete_domains_and_send_notif_emails(self, domains):
        deleted_domains = []
        for domain in domains:
            try:
                domain.deleteInEpp()
                domain.save()
                deleted_domains.append(domain)
            except Exception:
                logger.error(f"Failed to delete {domain.name}")

        if len(deleted_domains) > 0:
            self.send_domain_notifications_emails(deleted_domains)
        return deleted_domains

    def send_domain_notifications_emails(self, domains):
        """Send email to domain managers that the domain has been deleted"""

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
