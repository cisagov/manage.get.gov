"""

This command is intended to clean up any expired domain or portfolio invitations

- In dry-run mode (default), only logs what would be changed
- With --no-dry-run, deletes all portfolio and domain invitations older than 30 days
"""

import logging
import argparse
from django.core.management import BaseCommand
from registrar.models import UserPortfolioPermission, UserDomainRole
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Updates registrant contact info for any domains which are missing the info"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "When enabled (which is the default), does not call the registry; only reports what would be updated. "
                "Disable with --no-dry-run to perform updates."
                "For dry run: ./manage.py update_missing_registrant_contacts"
                "For not dry run: ./manage.py update_missing_registrant_contacts --no-dry-run"
            ),
        )
        parser.add_argument(
            "--target-type",
            "--target_type",
            required=False,
            help="Only delete invitations of a specific type ['portfolio', 'domain'].",
        )

    def handle(self, *args, **options):
        logger.debug("Running invitation clean up script")
        dry_run = bool(options.get("dry_run", True))
        target_type = options.get("target_type", None)

        if not target_type:
            self.clean_up_domain_invitations(dry_run)
            self.clean_up_portfolio_invitations(dry_run)

        else:
            if target_type == "domain":
                self.clean_up_domain_invitations(dry_run)
            elif target_type == "portfolio":
                self.clean_up_portfolio_invitations(dry_run)

    def clean_up_domain_invitations(self, dry_run):
        expired_invitations = UserDomainRole.objects.filter(
            status=UserDomainRole.Status.INVITED, expire_dt__lte=timezone.now()
        )
        logger.info(f"Found {expired_invitations.count()} expired Domain invitations")
        if expired_invitations:
            if not dry_run:
                for invitation in expired_invitations:
                    invitation.status = UserDomainRole.Status.EXPIRED
                UserDomainRole.objects.bulk_update(expired_invitations, ["status"])
                logger.info(f"Updated {expired_invitations.count()} Domain invitation(s) to expired status")
            else:
                logger.info("Expired Domain Invitations:")
                for invitation in expired_invitations:
                    logger.info(f"{invitation.user.email}")

    def clean_up_portfolio_invitations(self, dry_run):
        expired_invitations = UserPortfolioPermission.objects.filter(
            status=UserPortfolioPermission.Status.INVITED, expire_dt__lte=timezone.now()
        )
        logger.info(f"Found {expired_invitations.count()} expired Portfolio invitations")
        if expired_invitations:
            if not dry_run:
                for invitation in expired_invitations:
                    invitation.status = UserPortfolioPermission.Status.EXPIRED
                UserPortfolioPermission.objects.bulk_update(expired_invitations, ["status"])
                logger.info(f"Updated {expired_invitations.count()} Portfolio invitation(s) to expired status")
            else:
                for invitation in expired_invitations:
                    logger.info(f"{invitation.user.email}")
