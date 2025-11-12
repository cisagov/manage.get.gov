import logging

from datetime import timedelta, datetime
from django.core.management import BaseCommand
from django.utils import timezone
from registrar.models import Domain, UserDomainRole, UserPortfolioPermission
from registrar.models.user import UserPortfolioRoleChoices
from registrar.utility.email import send_templated_email, EmailSendingError
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Sends reminder emails to domain managers and organization admins "
        "if an approved domain is still in Unkown or DNS needed state 7 days after approval."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print emails that would be sent without actually sending them",
        )

    def _get_seven_days_ago_date_range(self, today):
        """Get the start and end datetime for exactly 7 days ago."""
        seven_days_ago_date = today - timedelta(days=7)
        seven_days_ago_start = datetime.combine(seven_days_ago_date, datetime.min.time())
        seven_days_ago_end = datetime.combine(seven_days_ago_date, datetime.max.time())

        return (
            timezone.make_aware(seven_days_ago_start),
            timezone.make_aware(seven_days_ago_end),
        )

    def _get_domain_manager_emails(self, domain):
        """Get list of domain manager email addresses for a domain"""
        return list(
            UserDomainRole.objects.filter(domain=domain, user__isnull=False)
            .values_list("user__email", flat=True)
            .distinct()
        )

    def _get_portfolio_admin_emails(self, portfolio):
        """Get list of portfolio admin email addresses, or empty list if no portfolio."""
        if not portfolio:
            return []

        return list(
            UserPortfolioPermission.objects.filter(
                portfolio=portfolio,
                roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            )
            .values_list("user__email", flat=True)
            .distinct()
        )

    def _send_email_for_domain(self, domain, domain_manager_emails, portfolio_admin_emails, approval_date, dryrun):
        """Send setup reminder email for a domain (or log in dry-run mode)."""
        template = "emails/domain_setup_reminder.txt"
        subject_template = "emails/domain_setup_reminder_subject.txt"

        context = {
            "domain": domain,
            "approval_date": approval_date,
        }

        try:
            if dryrun:
                rendered_subject = render_to_string(subject_template, context).strip()
                rendered_body = render_to_string(template, context)

                logger.info(
                    f"[DRYRUN]\n"
                    f"Would send email for domain {domain.name}\n"
                    f"TO: {domain_manager_emails}\n"
                    f"CC: {portfolio_admin_emails}\n"
                    f"Subject: {rendered_subject}\n"
                    f"Body:\n{rendered_body}"
                )
                return True
            else:
                send_templated_email(
                    template,
                    subject_template,
                    to_addresses=domain_manager_emails,
                    cc_addresses=portfolio_admin_emails,
                    context=context,
                )
                cc_message = f" and CC'd {len(portfolio_admin_emails)} org admin(s)" if portfolio_admin_emails else ""
                logger.info(f"Sent setup reminder email for domain {domain.name} to managers{cc_message}")
                return True
        except EmailSendingError as err:
            if not dryrun:
                logger.error(
                    "Failed to send domain setup reminder email:\n"
                    f" Subject template: {subject_template}\n"
                    f" TO: {', '.join(domain_manager_emails)}\n"
                    f" CC: {', '.join(portfolio_admin_emails)}\n"
                    f" Doamin: {domain.name}\n"
                    f" Error: {err}",
                    exc_info=True,
                )
                return True

    def handle(self, *args, **options):
        """
        How to run it in dry run mode:
        ./manage.py send_domain_setup_reminder --dry-run
        """
        dryrun = options.get("dry_run", False)
        all_emails_sent = True
        today = timezone.now().date()

        # Find domains created exactly 7 days ago
        seven_days_ago_start, seven_days_ago_end = self._get_seven_days_ago_date_range(today)

        domains = Domain.objects.filter(
            created_at__gte=seven_days_ago_start,
            created_at__lte=seven_days_ago_end,
            state__in=[Domain.State.UNKNOWN, Domain.State.DNS_NEEDED],
        ).exclude(state=Domain.State.DELETED)

        logger.info(f"Found {domains.count()} domains approved 7 days ago that still need DNS setup")

        approval_date = today - timedelta(days=7)
        for domain in domains:
            # Skip if domain doesn't have domain_info (shouldn't happen, but defensive)
            try:
                domain_info = domain.domain_info
            except Domain.domain_info.RelatedObjectDoesNotExist:
                logger.warning(f"Domain {domain.name} does not have domain_info, skipping")
                continue

            # Get domain manager emails
            domain_manager_emails = self._get_domain_manager_emails(domain)
            if not domain_manager_emails:
                logger.warning(f"Domain {domain.name} has no domain managers, skipping")
                continue

            # Get portfolio admin emails (only for enterprise domains)
            portfolio_admin_emails = self._get_portfolio_admin_emails(domain_info.portfolio)

            # Send email
            if not self._send_email_for_domain(
                domain,
                domain_manager_emails,
                portfolio_admin_emails,
                approval_date,
                dryrun,
            ):
                all_emails_sent = False

        if all_emails_sent:
            self.stdout.write(self.style.SUCCESS("All domain setup reminder emails sent successfully."))
        else:
            self.stderr.write(self.style.ERROR("Some domain setup reminder emails failed to sent."))
