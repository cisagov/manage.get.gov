import logging
from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from registrar.models import Domain, UserDomainRole, UserPortfolioPermission
from registrar.models.user import UserPortfolioRoleChoices
from registrar.utility.email import send_templated_email, EmailSendingError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Sends domain expiration warning emails to domain managers "
        "and portfolio managers at 30, 7, and 1 day(s) before expiration."
    )

    # This function will also be deleted, these are just testing params
    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Send emails for ALL domains with expiration dates, not just 30/7/1 days out (for testing only)",
        )
        parser.add_argument(
            "--test-email",
            type=str,
            help="Send all emails to this address (for testing only)",
        )

        parser.add_argument(
            "--test-cc-email",
            type=str,
            help="Optional: CC this email(for testing only)",
        )

    def handle(self, *args, **options):
        """
        How to run the code:
        ./manage.py send_expiring_soon_domains_notification --all
        --test-email=<your-email-here> --test-cc-email=<your-email-here+cc>
        For example:
        ./manage.py send_expiring_soon_domains_notification --all
        --test-email=rebecca.hsieh@truss.works --test-cc-email=rebecca.hsieh+cc@truss.works
        I've added to parameters so people can put in their own email, and it will trigger sending emails for all domains

        The "if" statement code is almost actual code, but some parts are removed and edited as it's JUST for testing
        and you'll see for example that the days_remaining is 0 (versus 30/7/1).

        The "else" statement is the actual code I'll be pushing to production/should be critqued please!
        """

        # These three lines below will be deleted, these are just for testing flags
        test_email = options.get("test_email")
        send_all = options.get("all")
        test_cc_email = options.get("test_cc_email")

        # Keep this line
        all_emails_sent = True

        if send_all:
            expiring_domains = Domain.objects.exclude(expiration_date__isnull=True)
            logger.info(f"[TEST MODE] Found {expiring_domains.count()} domains with any expiration date")

            # Bypassing
            for domain in expiring_domains:
                if domain.state == Domain.State.READY:
                    template = "emails/ready_and_expiring_soon.txt"
                    subject_template = "emails/ready_and_expiring_soon_subject.txt"
                elif domain.state in [Domain.State.DNS_NEEDED, Domain.State.UNKNOWN]:
                    template = "emails/dns_needed_or_unknown_expiring_soon.txt"
                    subject_template = "emails/dns_needed_or_unknown_expiring_soon_subject.txt"

                context = {
                    "domain": domain,
                    "days_remaining": 0,  # Faking for testing purposes!
                    "expiration_date": domain.expiration_date,
                }

                # -- GRAB DOMAIN MANAGER EMAILS --
                domain_manager_emails = list(
                    UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct()
                )

                # -- GRAB PORTFOLIO ADMIN EMAILS --
                user_ids = UserDomainRole.objects.filter(domain=domain).values_list("user", flat=True)
                portfolio_ids = UserPortfolioPermission.objects.filter(user__in=user_ids).values_list(
                    "portfolio", flat=True
                )
                portfolio_admin_emails = list(
                    UserPortfolioPermission.objects.filter(
                        portfolio__in=portfolio_ids,
                        roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
                    )
                    .values_list("user__email", flat=True)
                    .distinct()
                )

                # Printing the lists
                print(f"Domain managers for {domain.name}: {domain_manager_emails}")
                print(f"Portfolio admins for {domain.name}: {portfolio_admin_emails}")

                if test_email:
                    domain_manager_emails = [test_email]
                if test_cc_email:
                    portfolio_admin_emails = [test_cc_email]

                try:
                    send_templated_email(
                        template,
                        subject_template,
                        to_address=domain_manager_emails,
                        cc_addresses=portfolio_admin_emails,
                        context=context,
                    )
                    logger.info(f"Sent email for domain {domain.name} to managers and CC’d org admins")
                except EmailSendingError as e:
                    logger.warning(f"Failed to send email for domain {domain.name}. Reason: {e}")
                    all_emails_sent = False
        # This is the proper code and I'll remove the else after
        # It's in an else so we can run the trial code above
        # else:
        #     today = timezone.now().date()
        #     days_to_check = [30, 7, 1]
        #     all_emails_sent = True

        #     expiring_domains = Domain.objects.filter(
        #         expiration_date__in=[today + timedelta(days=days) for days in days_to_check]
        #     )
        #     logger.info(f"Found {expiring_domains.count()} domains expiring in 30, 7, or 1 days")
        #     for days_remaining in days_to_check:
        #         # Todays date + however many days away and then filter for that expiration date
        #         expiration_day = today + timedelta(days=days_remaining)
        #         expiring_domains = Domain.objects.filter(expiration_date=expiration_day)

        #         logger.info(f"Found {expiring_domains.count()} domains expiring in {days_remaining} days")

        #         # Choose which email template to use based on domain state
        #         for domain in expiring_domains:
        #             if domain.state == Domain.State.READY:
        #                 template = "emails/ready_and_expiring_soon.txt"
        #                 subject_template = "emails/ready_and_expiring_soon_subject.txt"
        #             elif domain.state in [Domain.State.DNS_NEEDED, Domain.State.UNKNOWN]:
        #                 template = "emails/dns_needed_or_unknown_expiring_soon.txt"
        #                 subject_template = "emails/dns_needed_or_unknown_expiring_soon_subject.txt"

        #             context = {
        #                 "domain": domain,
        #                 "days_remaining": days_remaining,
        #                 "expiration_date": domain.expiration_date,
        #             }

        #             # -- GRAB DOMAIN MANAGER EMAILS --
        #             domain_manager_emails = list(
        #                 UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct()
        #             )

        #             # -- GRAB PORTFOLIO ADMIN EMAILS --
        #             user_ids = UserDomainRole.objects.filter(domain=domain).values_list("user", flat=True)
        #             portfolio_ids = UserPortfolioPermission.objects.filter(user__in=user_ids).values_list(
        #                 "portfolio", flat=True
        #             )
        #             portfolio_admin_emails = list(
        #                 UserPortfolioPermission.objects.filter(
        #                     portfolio__in=portfolio_ids,
        #                     roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        #                 )
        #                 .values_list("user__email", flat=True)
        #                 .distinct()
        #             )

        #             try:
        #                 send_templated_email(
        #                     template,
        #                     subject_template,
        #                     to_address=domain_manager_emails,
        #                     cc_addresses=portfolio_admin_emails,
        #                     context=context,
        #                 )
        #                 logger.info(f"Sent email for domain {domain.name} to managers and CC’d org admins")
        #             except EmailSendingError as e:
        #                 logger.warning(f"Failed to send email for domain {domain.name}. Reason: {e}")
        #                 all_emails_sent = False

        if all_emails_sent:
            self.stdout.write(self.style.SUCCESS("All domain expiration emails sent successfully."))
        else:
            self.stderr.write(self.style.ERROR("Some domain expiration emails failed to send."))
