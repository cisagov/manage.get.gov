from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from auditlog.models import LogEntry as AuditLogEntry

from registrar.models import (
    Domain,
    DomainInvitation,
    Portfolio,
    PortfolioInvitation,
    UserDomainRole,
    UserPortfolioPermission,
)
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices

from .common import create_user, less_console_noise


class TestMigrateLegacyInvitationsCommand(TestCase):
    def setUp(self):
        self.user = create_user(username="inviter", email="inviter@example.gov")
        self.domain = Domain.objects.create(name="example.gov")
        self.portfolio = Portfolio.objects.create(requester=self.user, organization_name="Example Organization")

        self.domain_invitation = DomainInvitation.objects.create(
            email="domain-invitee@example.gov",
            domain=self.domain,
        )
        self.portfolio_invitation = PortfolioInvitation.objects.create(
            email="portfolio-invitee@example.gov",
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS],
        )

        invited_at = timezone.now() - timedelta(days=30)
        DomainInvitation.objects.filter(pk=self.domain_invitation.pk).update(created_at=invited_at)
        PortfolioInvitation.objects.filter(pk=self.portfolio_invitation.pk).update(created_at=invited_at)
        self.domain_invitation.refresh_from_db()
        self.portfolio_invitation.refresh_from_db()

        self._create_admin_log(self.domain_invitation)
        self._create_admin_log(self.portfolio_invitation)

    def _create_admin_log(self, invitation):
        LogEntry.objects.create(
            user=self.user,
            content_type=ContentType.objects.get_for_model(invitation),
            object_id=str(invitation.pk),
            object_repr=str(invitation),
            action_flag=ADDITION,
            change_message="Created invitation",
        )

    def test_dry_run_does_not_create_invitations(self):
        with less_console_noise():
            call_command("migrate_legacy_invitations")

        self.assertFalse(UserDomainRole.objects.exists())
        self.assertFalse(UserPortfolioPermission.objects.exists())

    @patch(
        "registrar.management.commands.utility.terminal_helper.TerminalHelper.prompt_for_execution",
        return_value=True,
    )
    def test_migrates_pending_invitations(self, _mock_prompt):
        with less_console_noise():
            call_command("migrate_legacy_invitations", dry_run=False)

        domain_role = UserDomainRole.objects.get(domain=self.domain)
        self.assertIsNone(domain_role.user)
        self.assertEqual(domain_role.email, self.domain_invitation.email)
        self.assertEqual(domain_role.role, UserDomainRole.Roles.MANAGER)
        self.assertEqual(domain_role.status, UserDomainRole.Status.INVITED)
        self.assertEqual(domain_role.invited_by, self.user)
        self.assertEqual(domain_role.invited_at, self.domain_invitation.created_at)

        permission = UserPortfolioPermission.objects.get(portfolio=self.portfolio)
        self.assertIsNone(permission.user)
        self.assertEqual(permission.email, self.portfolio_invitation.email)
        self.assertEqual(permission.roles, self.portfolio_invitation.roles)
        self.assertEqual(permission.additional_permissions, self.portfolio_invitation.additional_permissions)
        self.assertEqual(permission.status, UserPortfolioPermission.Status.INVITED)
        self.assertEqual(permission.invited_by, self.user)
        self.assertEqual(permission.invited_at, self.portfolio_invitation.created_at)

        self.assertTrue(
            AuditLogEntry.objects.get_for_object(domain_role).filter(action=AuditLogEntry.Action.CREATE).exists()
        )
        self.assertTrue(
            AuditLogEntry.objects.get_for_object(permission).filter(action=AuditLogEntry.Action.CREATE).exists()
        )

        # A second run should skip the matching records created by the first run.
        with less_console_noise():
            call_command("migrate_legacy_invitations", dry_run=False)

        self.assertEqual(UserDomainRole.objects.count(), 1)
        self.assertEqual(UserPortfolioPermission.objects.count(), 1)

    @patch(
        "registrar.management.commands.utility.terminal_helper.TerminalHelper.prompt_for_execution",
        return_value=True,
    )
    def test_does_not_migrate_non_pending_invitations(self, _mock_prompt):
        DomainInvitation.objects.create(
            email="retrieved@example.gov",
            domain=self.domain,
            status=DomainInvitation.DomainInvitationStatus.RETRIEVED,
        )
        DomainInvitation.objects.create(
            email="canceled@example.gov",
            domain=self.domain,
            status=DomainInvitation.DomainInvitationStatus.CANCELED,
        )
        PortfolioInvitation.objects.create(
            email="retrieved@example.gov",
            portfolio=self.portfolio,
            status=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED,
        )

        with less_console_noise():
            call_command("migrate_legacy_invitations", dry_run=False)

        self.assertFalse(
            UserDomainRole.objects.filter(email__in=["retrieved@example.gov", "canceled@example.gov"]).exists()
        )
        self.assertFalse(UserPortfolioPermission.objects.filter(email="retrieved@example.gov").exists())
