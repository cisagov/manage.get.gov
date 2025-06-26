from registrar.models import Domain, UserDomainRole, UserPortfolioPermission
from registrar.models.user import UserPortfolioRoleChoices
from django.utils import timezone
from datetime import timedelta

today = timezone.now().date()
days_to_check = [31,8,2]
for days_remaining in days_to_check:
    if days_remaining == 31:
        print("Domain, Days until expiration, Domain manager emails (To:), Portfolio admin emails (cc:)")
    domain_count = 0
    domains = Domain.objects.filter(expiration_date=today+timedelta(days=days_remaining))
    # print(f"Found {domains.count()} domains expiring in {days_remaining} days")
    
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
        domain_count += 1
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
        # print(
        #     f"[DRYRUN] Would send email for domain {domain.name} expiring in {days_remaining} days where "
        #     f"TO: {domain_manager_emails} || CC: {portfolio_admin_emails}"
        # )
        print(
            f"{domain.name};{days_remaining};{domain_manager_emails};{portfolio_admin_emails}"
        )
    # print(f"Number of domains expiring in {days_remaining} days: {domain_count}")

