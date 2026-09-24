"""Migrate pending legacy domain and portfolio invitations to the new role/permission models.

This command only handles invitations which are still pending. Retrieved and
canceled invitations are in the legacy domaininvitation and portfolioinvitation tables for historical reference.

- In dry-run mode, only logs what would be created
- With --no-dry-run, creates UserDomainRole and UserPortfolioPermission invitations
"""

import argparse
import logging

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import DomainInvitation, PortfolioInvitation, UserDomainRole, UserPortfolioPermission

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrates pending DomainInvitation and PortfolioInvitations to the new role/permission models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "When enabled (enabled by default), it does not create records and only reports what would be created. "
                "Disable with --no-dry-run to perform the migration and create corresponding roles/permissions."
            ),
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run", True))
        domain_invitations = (
            DomainInvitation.objects.filter(status=DomainInvitation.DomainInvitationStatus.INVITED)
            .select_related("domain")
            .order_by("id")
        )
        portfolio_invitations = (
            PortfolioInvitation.objects.filter(status=PortfolioInvitation.PortfolioInvitationStatus.INVITED)
            .select_related("portfolio")
            .order_by("id")
        )

        proposed = (
            "==Proposed Changes==\n"
            f"Pending domain invitations: {domain_invitations.count()}\n"
            f"Pending portfolio invitations: {portfolio_invitations.count()}\n"
            f"Dry run: {dry_run}\n\n"
            "Action: create pending UserDomainRole and UserPortfolioPermission invitations."
        )
        self._check_dry_run_and_prompt(dry_run, proposed)

        summary = {"created": 0, "would_create": 0, "skipped": 0, "failed": 0}
        seen_domain_invitations = set()
        seen_portfolio_invitations = set()

        # Mark each invitation as seen using its email and domain or portfolio ID.
        # This lets dry runs identify duplicate legacy invitations without creating records.
        for invitation in domain_invitations.iterator():
            key = (invitation.email.lower(), invitation.domain_id)
            duplicate_legacy_invitation = key in seen_domain_invitations
            result = self._migrate_domain_invitation(invitation, dry_run, duplicate_legacy_invitation)
            summary[result] += 1
            seen_domain_invitations.add(key)

        for invitation in portfolio_invitations.iterator():
            key = (invitation.email.lower(), invitation.portfolio_id)
            duplicate_legacy_invitation = key in seen_portfolio_invitations
            result = self._migrate_portfolio_invitation(invitation, dry_run, duplicate_legacy_invitation)
            summary[result] += 1
            seen_portfolio_invitations.add(key)

        header = "FINISHED (DRY RUN): Migrate legacy invitations" if dry_run else "FINISHED: Migrate legacy invitations"
        logger.info("============= %s =============", header)
        logger.info("Created: %s", summary["created"])
        logger.info("Would create: %s", summary["would_create"])
        logger.info("Skipped: %s", summary["skipped"])
        if summary["failed"]:
            logger.warning("Failed: %s", summary["failed"])

    def _check_dry_run_and_prompt(self, dry_run, proposed):
        if dry_run:
            logger.info(
                "%sDRY RUN:%s No invitations will be created.\n%s",
                TerminalColors.YELLOW,
                TerminalColors.ENDC,
                proposed,
            )
        else:
            TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=True,
                prompt_message=proposed,
                prompt_title="Migrate pending legacy domain and portfolio invitations",
            )

    def _migrate_domain_invitation(self, invitation, dry_run, duplicate_legacy_invitation):
        try:
            if duplicate_legacy_invitation:
                logger.info("Skipping duplicate DomainInvitation id=%s.", invitation.pk)
                return "skipped"

            if self._matching_domain_role_exists(invitation):
                logger.info("Skipping DomainInvitation id=%s because a matching role exists.", invitation.pk)
                return "skipped"

            if dry_run:
                logger.info(
                    "Would create UserDomainRole from DomainInvitation id=%s for %s on domain id=%s.",
                    invitation.pk,
                    invitation.email,
                    invitation.domain_id,
                )
                return "would_create"

            with transaction.atomic():
                domain_role = UserDomainRole.objects.create(
                    user=None,
                    domain=invitation.domain,
                    role=UserDomainRole.Roles.MANAGER,
                    status=UserDomainRole.Status.INVITED,
                    invited_by_id=self._get_invited_by_id(invitation),
                    invited_at=invitation.created_at,
                    email=invitation.email,
                )
            logger.info(
                "Created UserDomainRole id=%s from DomainInvitation id=%s.",
                domain_role.pk,
                invitation.pk,
            )
            return "created"
        except Exception:
            logger.exception("Failed to migrate DomainInvitation id=%s.", invitation.pk)
            return "failed"

    def _migrate_portfolio_invitation(self, invitation, dry_run, duplicate_legacy_invitation):
        try:
            if duplicate_legacy_invitation:
                logger.info("Skipping duplicate PortfolioInvitation id=%s.", invitation.pk)
                return "skipped"

            if self._matching_portfolio_permission_exists(invitation):
                logger.info("Skipping PortfolioInvitation id=%s because a matching permission exists.", invitation.pk)
                return "skipped"

            if dry_run:
                logger.info(
                    "Would create UserPortfolioPermission from PortfolioInvitation id=%s for %s on portfolio id=%s.",
                    invitation.pk,
                    invitation.email,
                    invitation.portfolio_id,
                )
                return "would_create"

            with transaction.atomic():
                permission = UserPortfolioPermission.objects.create(
                    user=None,
                    portfolio=invitation.portfolio,
                    roles=invitation.roles,
                    additional_permissions=invitation.additional_permissions,
                    status=UserPortfolioPermission.Status.INVITED,
                    invited_by_id=self._get_invited_by_id(invitation),
                    invited_at=invitation.created_at,
                    email=invitation.email,
                )
            logger.info(
                "Created UserPortfolioPermission id=%s from PortfolioInvitation id=%s.",
                permission.pk,
                invitation.pk,
            )
            return "created"
        except Exception:
            logger.exception("Failed to migrate PortfolioInvitation id=%s.", invitation.pk)
            return "failed"

    def _matching_domain_role_exists(self, invitation):
        return (
            UserDomainRole.objects.filter(domain=invitation.domain)
            .filter(Q(email__iexact=invitation.email) | Q(user__email__iexact=invitation.email))
            .exists()
        )

    def _matching_portfolio_permission_exists(self, invitation):
        return (
            UserPortfolioPermission.objects.filter(portfolio=invitation.portfolio)
            .filter(Q(email__iexact=invitation.email) | Q(user__email__iexact=invitation.email))
            .exists()
        )

    def _get_invited_by_id(self, invitation):
        # Legacy invitations do not have an invited_by field. When available, use the user from
        # the Django admin creation log, which is also how member exports find the inviter.
        content_type = ContentType.objects.get_for_model(invitation)
        return (
            LogEntry.objects.filter(
                content_type=content_type,
                object_id=str(invitation.pk),
                action_flag=ADDITION,
            )
            .order_by("action_time")
            .values_list("user_id", flat=True)
            .first()
        )
