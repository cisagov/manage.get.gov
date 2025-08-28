import logging

from datetime import timedelta

from django.core.management import BaseCommand

from django.utils import timezone

from registrar.models import Domain, UserDomainRole, UserPortfolioPermission
from registrar.models.user import UserPortfolioRoleChoices
from registrar.utility.email import send_templated_email, EmailSendingError
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Sends domain expiration warning emails to domain managers "
        "and portfolio managers at 30, 7, and 1 day(s) before expiration."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print emails that would be sent without actually sending them",
        )

    def handle(self, *args, **options):
        """
        How to run it in dry run mode:
        ./manage.py send_expiring_soon_domains_notification --dry-run
        """
        dryrun = options.get("dry_run", False)

        all_emails_sent = True
        today = timezone.now().date()

        days_to_check = [30, 7, 1]
        expiring_domains = Domain.objects.filter(expiration_date__in=[today + timedelta(days=d) for d in days_to_check])
        logger.info(f"Found {expiring_domains.count()} domains expiring in 30, 7, or 1 days")

        for days_remaining in days_to_check:

            expiration_day = today + timedelta(days=days_remaining)
            domains = Domain.objects.filter(expiration_date=expiration_day)

            logger.info(f"Found {domains.count()} domains expiring in {days_remaining} days")

            for domain in domains:
                if domain.state == Domain.State.READY:
                    template = "emails/ready_and_expiring_soon.txt"
                    subject_template = "emails/ready_and_expiring_soon_subject.txt"
                elif domain.state in [Domain.State.DNS_NEEDED, Domain.State.UNKNOWN]:
                    template = "emails/dns_needed_or_unknown_expiring_soon.txt"
                    subject_template = "emails/dns_needed_or_unknown_expiring_soon_subject.txt"
                else:
                    continue

                context = {
                    "domain": domain,
                    "days_remaining": days_remaining,
                    "expiration_date": domain.expiration_date,
                }

                # -- GRAB DOMAIN MANAGER EMAILS --
                domain_manager_emails = list(
                    UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct()
                )

                # -- GRAB PORTFOLIO ADMIN EMAILS --
                portfolio_id = domain.domain_info.portfolio_id
                portfolio_admin_emails = list(
                    UserPortfolioPermission.objects.filter(
                        portfolio_id=portfolio_id,
                        roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
                    )
                    .values_list("user__email", flat=True)
                    .distinct()
                )

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
                    else:
                        send_templated_email(
                            template,
                            subject_template,
                            to_addresses=domain_manager_emails,
                            cc_addresses=portfolio_admin_emails,
                            context=context,
                        )
                        logger.info(f"Sent email for domain {domain.name} to managers and CC’d org admins")
                except EmailSendingError as err:
                    if not dryrun:
                        logger.error(
                            "Failed to send expiring soon email(s):\n"
                            f"  Subject template: {subject_template}\n"
                            f"  To: {', '.join(domain_manager_emails)}\n"
                            f"  CC: {', '.join(portfolio_admin_emails)}\n"
                            f"  Domain: {domain.name}\n"
                            f"  Error: {err}",
                            exc_info=True,
                        )
                        all_emails_sent = False

        if all_emails_sent:
            self.stdout.write(self.style.SUCCESS("All domain expiration emails sent successfully."))
        else:
            self.stderr.write(self.style.ERROR("Some domain expiration emails failed to send."))
