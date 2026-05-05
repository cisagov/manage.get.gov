import logging
from django.core.management import BaseCommand

from django.utils import timezone
from datetime import timedelta

from registrar.models import Domain, UserDomainRole, UserPortfolioPermission
from registrar.models.user import UserPortfolioRoleChoices
from registrar.utility.email import send_templated_email, EmailSendingError
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Sends post-expiration emails to domain managers and portfolio managers for "
        "domains in 'Ready' state that are expired."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print emails that would be sent without actually sending them",
        )

        parser.add_argument(
            "--all-expired",
            action="store_true",
            help="Send emails to all expired Ready domains, not just those that expired today.",
        )

        parser.add_argument("--domain", help="Run for a specific domain name only (e.g. example.gov)")

    def _get_expired_domains(self, today, options):
        if options.get("domain"):
            return Domain.objects.filter(
                name=options.get("domain"),
                expiration_date__lt=today,
                state=Domain.State.READY,
            )
        elif options.get("all_expired"):
            return Domain.objects.filter(
                expiration_date__lt=today,
                state=Domain.State.READY,
            )
        else:
            return Domain.objects.filter(
                expiration_date=today,
                state=Domain.State.READY,
            )

    def _get_admin_emails(self, domain):
        portfolio_id = domain.domain_info.portfolio_id
        if portfolio_id:
            return list(
                UserPortfolioPermission.objects.filter(
                    portfolio_id=portfolio_id,
                    roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
                )
                .values_list("user__email", flat=True)
                .distinct()
            )
        else:
            senior_official = domain.domain_info.senior_official
            return [senior_official.email] if senior_official and senior_official.email else []

    def handle(self, *args, **options):
        """How to run it in dry run mode:
        ./manage.py send_post_expiration_notification --dry-run
        """
        dryrun = options.get("dry_run", False)

        all_emails_sent = True
        today = timezone.now().date()
        bcc = "help@get.gov"

        expired_domains = self._get_expired_domains(today, options)
        logger.info(f"Found {expired_domains.count()} expired domains that are in 'Ready' state.")

        # first_domain used to output sample email template.
        first_domain = expired_domains.first()

        for domain in expired_domains:

            template = "emails/ready_and_expired.txt"
            subject_template = "emails/ready_and_expired_subject.txt"

            # -- GRAB DOMAIN MANAGER EMAILS --
            domain_manager_emails = list(
                UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct()
            )

            # -- GRAB PORTFOLIO ADMIN EMAILS --
            admin_emails = self._get_admin_emails(domain)

            context = {
                "domain": domain,
                "expiration_date": domain.expiration_date,
                "domain_manager_emails": domain_manager_emails,
                "one_week_after_expiration": domain.expiration_date + timedelta(days=7),
            }

            try:
                if dryrun:
                    logger.info(
                        f"[DRYRUN]\n"
                        f"{domain.name} would be sent to\n"
                        f"TO: {domain_manager_emails}, "
                        f"CC: {admin_emails}, "
                        f"BCC: {bcc}"
                    )
                else:
                    send_templated_email(
                        template,
                        subject_template,
                        to_addresses=domain_manager_emails,
                        cc_addresses=admin_emails,
                        bcc_address=bcc,
                        context=context,
                    )
                    logger.info(f"Sent email for domain {domain.name} to managers and CC'd org admins")
            except EmailSendingError as err:
                if not dryrun:
                    logger.error(
                        "Failed to send post-expiration email(s):\n"
                        f"  Subject template: {subject_template}\n"
                        f"  To: {'. '.join(domain_manager_emails)}\n"
                        f"  CC: {', '.join(admin_emails)}\n"
                        f"  BCC: {bcc}\n"
                        f"  Domain: {domain.name}\n"
                        f"  Error: {err}",
                        exc_info=True,
                    )
                all_emails_sent = False

        if not expired_domains:
            self.stdout.write(self.style.SUCCESS("No expired Ready domains found."))
        elif all_emails_sent:
            if first_domain and dryrun:
                rendered_subject = render_to_string(subject_template, context).strip()
                rendered_body = render_to_string(template, context)
                self.stdout.write(f"Sample email:\n" f"Subject:{rendered_subject}\n" f"Body:{rendered_body}")
            self.stdout.write(self.style.SUCCESS("All post-expiration emails sent successfully."))
        else:
            self.stderr.write(self.style.ERROR("Some post-expiration emails failed to send."))
