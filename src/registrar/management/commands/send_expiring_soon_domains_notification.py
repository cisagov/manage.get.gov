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

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Send emails for all domains with expiration dates, not just 30/7/1 days out (for testing)",
        )
        parser.add_argument(
            "--test-email",
            type=str,
            help="Send all emails to this address (for testing only)",
        )

        parser.add_argument(
            "--test-cc-email",
            type=str,
            help="Optional: CC this email when using --test-email (for testing only)",
        )

    def handle(self, *args, **options):
        """
        How to run the code:
        ./manage.py send_expiring_soon_domains_notification --all --test-email=<your-email-here>
        For example:
        ./manage.py send_expiring_soon_domains_notification --all --test-email=rebecca.hsieh@truss.works
        ./manage.py send_expiring_soon_domains_notification --all --test-email=rebecca.hsieh@truss.works --test-cc-email=rebecca.hsieh+cc@truss.works
        I've added to parameters so people can put in their own email, and it will trigger sending emails for all domains

        The "if" statement code is almost actual code, but some parts are removed and edited as it's JUST for testing
        and you'll see for example that the days_remaining is 0 (versus 30/7/1).

        The "else" statement is the actual code I'll be pushing to production/should be critqued please!
        """

        # These two lines below will be deleted
        test_email = options.get("test_email")
        send_all = options.get("all")
        test_cc_email = options.get("test_cc_email")

        all_emails_sent = True

        if send_all:
            expiring_domains = Domain.objects.exclude(expiration_date__isnull=True)
            logger.info(f"[TEST MODE] Found {expiring_domains.count()} domains with any expiration date")

            # Bypass loop and handle everything in one go
            for domain in expiring_domains:
                if domain.state == Domain.State.READY:
                    template = "emails/ready_and_expiring_soon.txt"
                    subject_template = "emails/ready_and_expiring_soon_subject.txt"
                elif domain.state in [Domain.State.DNS_NEEDED, Domain.State.UNKNOWN]:
                    template = "emails/dns_needed_or_unknown_expiring_soon.txt"
                    subject_template = "emails/dns_needed_or_unknown_expiring_soon_subject.txt"
                else:
                    print("!!!!! We really shouldn't come into here but in case?????")
                    template = "emails/ready_and_expiring_soon.txt"
                    subject_template = "emails/ready_and_expiring_soon_subject.txt"

                context = {
                    "domain": domain,
                    "days_remaining": 0,  # Faking for testing
                    "expiration_date": domain.expiration_date,
                }

                # user_domain_roles = UserDomainRole.objects.filter(domain=domain)
                # domain_manager_emails = set(role.user.email for role in user_domain_roles)

                # portfolio = getattr(domain, "portfolio", None)

                # admin_emails = set()
                # if portfolio:
                #     print("!!!! Do we come into this if portfolio check?")
                #     admin_roles = UserPortfolioPermission.objects.filter(
                #         portfolio=portfolio,
                #         roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
                #     )
                #     admin_emails = set(role.user.email for role in admin_roles)

                # to_address = [test_email] if test_email else list(domain_manager_emails)
                # cc_addresses = []
                # print("!!! Do we even get to the addresses?")
                # if test_email:
                #     if test_cc_email:
                #         cc_addresses.append(test_cc_email)
                # else:
                #     cc_addresses = list(admin_emails)

                # logger.debug({
                #     "template": template,
                #     "subject_template": subject_template,
                #     "to": list(domain_manager_emails),
                #     "cc": list(admin_emails),
                #     "context": context,
                # })

                # print({
                #     "template": template,
                #     "subject_template": subject_template,
                #     "to": list(domain_manager_emails),
                #     "cc": list(admin_emails),
                #     "context": context,
                # })

                user_domain_roles = UserDomainRole.objects.filter(domain=domain)

                for user_domain_role in user_domain_roles:
                    print("!!!!! Do we come into the user domain role section")
                    user = user_domain_role.user

                    logger.info(
                        f"Sending email to: {test_email if test_email else user.email} for domain {domain.name}"
                    )

                    try:
                        send_templated_email(
                            template,
                            subject_template,
                            to_address=test_email or user.email,
                            context=context,
                        )
                        logger.info(f"Emailed domain manager {user.email} for domain {domain.name}")
                    except EmailSendingError:
                        logger.warning(f"Failed to email domain manager {user.email} for domain {domain.name}")
                        all_emails_sent = False

                    user_portfolio_ids = UserPortfolioPermission.objects.filter(user=user).values_list(
                        "portfolio", flat=True
                    )

                    admin_roles = UserPortfolioPermission.objects.filter(
                        portfolio__in=user_portfolio_ids,
                        roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
                    )

                    for admin_role in admin_roles:
                        print("!!!!! Do we come into the admin role section")
                        admin_email = admin_role.user.email

                        try:
                            send_templated_email(
                                template,
                                subject_template,
                                to_address=test_cc_email or admin_email,
                                context=context,
                            )
                            logger.info(f"Emailed portfolio admin {admin_email} for domain {domain.name}")
                        except EmailSendingError:
                            logger.warning(f"Failed to email portfolio admin {admin_email} for domain {domain.name}")
                            all_emails_sent = False

                # try:
                #     send_templated_email(
                #         template,
                #         subject_template,
                #         to_address=to_address,
                #         cc_addresses=cc_addresses,
                #         context=context,
                #     )
                #     logger.info(
                #         f"Emailed domain managers {domain_manager_emails} and portfolio admins {admin_emails} for domain {domain.name}."
                #     )
                # except EmailSendingError as e:
                #     logger.warning(f"Failed to email domain managers and admins for domain {domain.name}. Reason is {e}")
                #     all_emails_sent = False

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

        #             ### Emailing domain manager section
        #             user_domain_roles = UserDomainRole.objects.filter(domain=domain)
        #             domain_manager_emails = set(role.user.email for role in user_domain_roles)

        #             ### Emailing portfolio admin section
        #             # We nest this as for each domain manager,
        #             # we also notify the admins of the porfolio the domain manager belongs to

        #             # Get the domain's associated portfolio (if any)
        #             portfolio = getattr(domain, "portfolio", None)

        #             admin_emails = set()
        #             if portfolio:
        #                 # Email portfolio admins of those portfolios
        #                 admin_roles = UserPortfolioPermission.objects.filter(
        #                     portfolio=portfolio,
        #                     roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        #                 )
        #                 admin_emails = set(role.user.email for role in admin_roles)

        #             # Send one email per domain with domain managers as "to" and admins as "cc"
        #             try:
        #                 send_templated_email(
        #                     template,
        #                     subject_template,
        #                     to_address=list(domain_manager_emails),
        #                     cc_addresses=list(admin_emails),
        #                     context=context,
        #                 )
        #                 logger.info(
        #                     f"Emailed domain managers {domain_manager_emails} and portfolio admins {admin_emails} for domain {domain.name}"
        #                 )
        #             except EmailSendingError:
        #                 logger.warning(f"Failed to email domain managers and admins for domain {domain.name}")
        #                 all_emails_sent = False

        if all_emails_sent:
            self.stdout.write(self.style.SUCCESS("All domain expiration emails sent successfully."))
        else:
            self.stderr.write(self.style.ERROR("Some domain expiration emails failed to send."))
