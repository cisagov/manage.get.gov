import logging

from datetime import timedelta

from django.core.management import BaseCommand

from django.utils import timezone

from registrar.management.commands.utility.terminal_helper import TerminalColors
from registrar.models import Domain, UserDomainRole, UserPortfolioPermission
from registrar.models.user import UserPortfolioRoleChoices
from registrar.utility.email import send_templated_email, EmailSendingError
from django.template.loader import render_to_string
from django.db.models import Q

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

    def handle(self, *args, **options):  # noqa: C901
        """
        How to run it in dry run mode:
        ./manage.py send_expiring_soon_domains_notification --dry-run
        """
        dryrun = options.get("dry_run", False)

        all_emails_sent = True
        today = timezone.now().date()

        days_to_check = [30, 7, 1]

        # Check for expiring domains that have an expiration date in the next 30, 7, or 1 days,
        # as well as UNKNOWN domains with null expiration date
        # NOTE: We want to re-examine setting an expiration date for UNKNOWN state domains,
        # which would allow us to remove the check for null expiration dates here and in
        # delete_expired_domains_not_setup.py
        expiring_domains = Domain.objects.filter(
            Q(expiration_date__in=[today + timedelta(days=d) for d in days_to_check])
            | Q(expiration_date__isnull=True, state__in=[Domain.State.UNKNOWN])
        )
        logger.info(f"Found {expiring_domains.count()} domains expiring in 30, 7, or 1 days")

        # For each domain that is expiring soon, send an email to the domain managers and CC organization admins.
        # Check each day threshold separately so that the email content can be customized based on
        # how many days until expiration
        for days_remaining in days_to_check:

            forecast_expiration_date = today + timedelta(days=days_remaining)
            domains = Domain.objects.filter(
                Q(expiration_date=forecast_expiration_date)
                | Q(
                    expiration_date__isnull=True,
                    state__in=[Domain.State.UNKNOWN],
                    created_at=forecast_expiration_date - timedelta(days=365),
                )
            )
            logger.info(f"Found {domains.count()} domains expiring in {days_remaining} days")

            for domain in domains:
                effective_expiration = domain.expiration_date

                logger.info(
                    f"{TerminalColors.MAGENTA}Domain {domain.name} (id: {domain.id})"
                    f"has status {domain.state}, expiration date {domain.expiration_date},"
                    f"and creation date {domain.created_at}{TerminalColors.ENDC}"
                )
                if domain.expiration_date is None:
                    effective_expiration = (domain.created_at + timedelta(days=365)).date()
                    logger.warning(
                        f"{TerminalColors.YELLOW}Domain {domain.name} (id: {domain.id}) has a"
                        f"null expiration date in state {domain.state}. "
                        f"Using creation date +  1yr instead for an effective expiration of"
                        f"{effective_expiration}.{TerminalColors.ENDC}"
                    )

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
                    "expiration_date": effective_expiration,
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
                        logger.info(
                            f"{TerminalColors.OKGREEN}Sent email {template} with context {context}"
                            f"for domain {domain.name} to managers and CC’d org admins{TerminalColors.ENDC}"
                        )
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
