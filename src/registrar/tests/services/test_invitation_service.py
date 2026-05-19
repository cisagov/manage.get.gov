from django.test import TestCase
from unittest.mock import patch

from registrar.models import (
    Domain,
    Portfolio,
    User,
    UserDomainRole,
    UserPortfolioPermission,
)
from registrar.services.invitation_service import (
    create_portfolio_permission_or_invitation,
    invite_to_portfolio,
    invite_to_domain,
    invite_to_domains_bulk,
    get_pending_invitations,
    accept_portfolio_invitation,
    accept_domain_invitation,
    cancel_domain_invitation,
    cancel_portfolio_invitation,
    reactivate_domain_invitation,
    check_duplicate_domain_invitation,
    check_duplicate_portfolio_invitation,
)
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
from registrar.utility.email import EmailSendingError
from registrar.utility.errors import InvitationError


class TestInvitationService(TestCase):
    """Test suite for invitation service layer functions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username="test_invitee", email="invitee@example.com")
        self.requestor = User.objects.create(username="test_requestor", email="requestor@example.com")
        self.portfolio = Portfolio.objects.create(
            requester=self.requestor,
            organization_name="Test Organization",
            organization_type="federal",
        )
        self.domain = Domain.objects.create(name="test.gov")

    @patch("registrar.services.invitation_service." "send_portfolio_invitation_email")
    def test_invite_to_portfolio_creates_permission(self, mock_send_email):
        """invite_to_portfolio creates a UserPortfolioPermission."""
        mock_send_email.return_value = True
        email = "invitee@example.com"
        roles = [UserPortfolioRoleChoices.ORGANIZATION_MEMBER]

        permission = invite_to_portfolio(
            email=email,
            portfolio=self.portfolio,
            requestor=self.requestor,
            roles=roles,
        )

        self.assertIsNotNone(permission)
        self.assertEqual(permission.email, email)
        self.assertEqual(permission.user, self.user)
        self.assertEqual(permission.portfolio, self.portfolio)
        self.assertEqual(permission.roles, roles)
        self.assertEqual(permission.status, UserPortfolioPermission.Status.ACCEPTED)
        self.assertEqual(permission.invited_by, self.requestor)
        mock_send_email.assert_called_once()

    @patch("registrar.services.invitation_service." "send_portfolio_invitation_email")
    def test_create_portfolio_permission_for_existing_user_without_email(self, mock_send_email):
        """create_portfolio_permission_or_invitation can add existing users without email."""
        roles = [UserPortfolioRoleChoices.ORGANIZATION_MEMBER]

        permission, email_was_sent = create_portfolio_permission_or_invitation(
            email=self.user.email,
            portfolio=self.portfolio,
            requestor=self.requestor,
            roles=roles,
            send_email=False,
        )

        self.assertEqual(permission.user, self.user)
        self.assertEqual(permission.email, self.user.email)
        self.assertEqual(permission.status, UserPortfolioPermission.Status.ACCEPTED)
        self.assertIsNone(permission.invited_by)
        self.assertTrue(email_was_sent)
        mock_send_email.assert_not_called()

    @patch("registrar.services.invitation_service." "send_portfolio_invitation_email")
    def test_create_portfolio_invitation_for_unknown_email_forces_email(self, mock_send_email):
        """create_portfolio_permission_or_invitation always sends email for unknown users."""
        mock_send_email.return_value = True
        email = "new-invitee@example.com"
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

        permission, email_was_sent = create_portfolio_permission_or_invitation(
            email=email,
            portfolio=self.portfolio,
            requestor=self.requestor,
            roles=roles,
            send_email=False,
        )

        self.assertIsNone(permission.user)
        self.assertEqual(permission.email, email)
        self.assertEqual(permission.status, UserPortfolioPermission.Status.INVITED)
        self.assertEqual(permission.invited_by, self.requestor)
        self.assertTrue(email_was_sent)
        mock_send_email.assert_called_once()

    def test_create_portfolio_permission_uses_user_email_before_invitation_email(self):
        """create_portfolio_permission_or_invitation prefers user email once an invitation has a user."""
        permission = UserPortfolioPermission(
            user=self.user,
            email="old-invitee@example.com",
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            status=UserPortfolioPermission.Status.ACCEPTED,
        )

        saved_permission, email_was_sent = create_portfolio_permission_or_invitation(
            email=None,
            portfolio=self.portfolio,
            requestor=self.requestor,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            send_email=False,
            permission=permission,
        )

        self.assertEqual(saved_permission.email, self.user.email)
        self.assertTrue(email_was_sent)

    @patch("registrar.services.invitation_service." "send_portfolio_invitation_email")
    def test_create_portfolio_invitation_does_not_set_details_when_email_fails(self, mock_send_email):
        """create_portfolio_permission_or_invitation records invite details only after email succeeds."""
        mock_send_email.side_effect = EmailSendingError("Could not send email.")
        permission = UserPortfolioPermission(
            email="new-invitee@example.com",
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            status=UserPortfolioPermission.Status.INVITED,
        )

        with self.assertRaises(EmailSendingError):
            create_portfolio_permission_or_invitation(
                email=None,
                portfolio=self.portfolio,
                requestor=self.requestor,
                roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
                send_email=True,
                permission=permission,
            )

        self.assertIsNone(permission.invited_by)
        self.assertIsNone(permission.invited_at)

    def test_create_portfolio_permission_duplicate_raises_invitation_error(self):
        """create_portfolio_permission_or_invitation rejects duplicate portfolio access."""
        roles = [UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        UserPortfolioPermission.objects.create(
            user=self.user,
            email=self.user.email,
            portfolio=self.portfolio,
            roles=roles,
            status=UserPortfolioPermission.Status.ACCEPTED,
        )

        with self.assertRaises(InvitationError) as context:
            create_portfolio_permission_or_invitation(
                email=self.user.email,
                portfolio=self.portfolio,
                requestor=self.requestor,
                roles=roles,
            )

        self.assertIn("existing invitation or is already a member", str(context.exception))

    @patch("registrar.services.invitation_service." "send_domain_invitation_email")
    def test_invite_to_domain_creates_role(self, mock_send_email):
        """invite_to_domain creates a UserDomainRole."""
        email = "invitee@example.com"
        role = UserDomainRole.Roles.MANAGER

        domain_role = invite_to_domain(
            email=email,
            domain=self.domain,
            requestor=self.requestor,
            role=role,
        )

        self.assertIsNotNone(domain_role)
        self.assertEqual(domain_role.email, email)
        self.assertEqual(domain_role.domain, self.domain)
        self.assertEqual(domain_role.role, role)
        self.assertEqual(domain_role.status, UserDomainRole.Status.INVITED)
        mock_send_email.assert_called_once()

    @patch("registrar.services.invitation_service." "send_domain_invitation_email")
    def test_invite_to_domains_bulk_creates_multiple_roles(self, mock_send_email):
        """invite_to_domains_bulk creates multiple UserDomainRole objects."""
        email = "invitee@example.com"
        domain2 = Domain.objects.create(name="test2.gov")
        domain3 = Domain.objects.create(name="test3.gov")
        domains = [self.domain, domain2, domain3]

        domain_roles = invite_to_domains_bulk(
            email=email,
            domains=domains,
            requestor=self.requestor,
            role=UserDomainRole.Roles.MANAGER,
        )

        self.assertEqual(len(domain_roles), 3)
        for domain_role in domain_roles:
            self.assertEqual(domain_role.email, email)
            self.assertEqual(domain_role.status, UserDomainRole.Status.INVITED)
        mock_send_email.assert_called_once()

    @patch("registrar.services.invitation_service.send_portfolio_invitation_email")
    def test_get_pending_invitations_returns_invitations(self, mock_send_email):
        """get_pending_invitations returns user's invitations."""
        mock_send_email.return_value = True
        email = "pending@example.com"

        # Create invitation
        invite_to_portfolio(
            email=email,
            portfolio=self.portfolio,
            requestor=self.requestor,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        pending_user = User.objects.create(username="pending_user", email=email)

        result = get_pending_invitations(pending_user)

        self.assertEqual(len(result["portfolio_permissions"]), 1)
        self.assertEqual(result["portfolio_permissions"][0].email, email)

    def test_accept_portfolio_invitation_updates_status(self):
        """accept_portfolio_invitation updates status to ACCEPTED."""
        # Create invitation
        permission = UserPortfolioPermission.objects.create(
            email=self.user.email,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            status=UserPortfolioPermission.Status.INVITED,
            invited_by=self.requestor,
        )

        result = accept_portfolio_invitation(self.user, self.portfolio)

        self.assertIsNotNone(result)
        permission.refresh_from_db()
        self.assertEqual(permission.status, UserPortfolioPermission.Status.ACCEPTED)
        self.assertEqual(permission.user, self.user)

    def test_accept_domain_invitation_updates_status(self):
        """accept_domain_invitation updates status to ACCEPTED."""
        # Create invitation
        domain_role = UserDomainRole.objects.create(
            email=self.user.email,
            domain=self.domain,
            role=UserDomainRole.Roles.MANAGER,
            status=UserDomainRole.Status.INVITED,
            invited_by=self.requestor,
        )

        result = accept_domain_invitation(self.user, self.domain)

        self.assertIsNotNone(result)
        domain_role.refresh_from_db()
        self.assertEqual(domain_role.status, UserDomainRole.Status.ACCEPTED)
        self.assertEqual(domain_role.user, self.user)

    def test_cancel_domain_invitation_updates_status(self):
        """cancel_domain_invitation updates status to REJECTED."""
        email = "invitee@example.com"
        UserDomainRole.objects.create(
            email=email,
            domain=self.domain,
            role=UserDomainRole.Roles.MANAGER,
            status=UserDomainRole.Status.INVITED,
            invited_by=self.requestor,
        )

        result = cancel_domain_invitation(email, self.domain)

        self.assertTrue(result)
        domain_role = UserDomainRole.objects.get(email=email, domain=self.domain)
        self.assertEqual(domain_role.status, UserDomainRole.Status.REJECTED)

    def test_cancel_portfolio_invitation_updates_status(self):
        """cancel_portfolio_invitation updates status to REJECTED."""
        email = "invitee@example.com"
        UserPortfolioPermission.objects.create(
            email=email,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            status=UserPortfolioPermission.Status.INVITED,
            invited_by=self.requestor,
        )

        result = cancel_portfolio_invitation(email, self.portfolio)

        self.assertTrue(result)
        permission = UserPortfolioPermission.objects.get(email=email, portfolio=self.portfolio)
        self.assertEqual(permission.status, UserPortfolioPermission.Status.REJECTED)

    def test_reactivate_domain_invitation_updates_status(self):
        """reactivate_domain_invitation updates status to INVITED."""
        email = "invitee@example.com"
        UserDomainRole.objects.create(
            email=email,
            domain=self.domain,
            role=UserDomainRole.Roles.MANAGER,
            status=UserDomainRole.Status.REJECTED,
            invited_by=self.requestor,
        )

        result = reactivate_domain_invitation(email, self.domain)

        self.assertTrue(result)
        domain_role = UserDomainRole.objects.get(email=email, domain=self.domain)
        self.assertEqual(domain_role.status, UserDomainRole.Status.INVITED)

    def test_check_duplicate_domain_invitation_returns_true(self):
        """check_duplicate_domain_invitation finds existing invitation."""
        email = "invitee@example.com"
        UserDomainRole.objects.create(
            email=email,
            domain=self.domain,
            role=UserDomainRole.Roles.MANAGER,
            status=UserDomainRole.Status.INVITED,
            invited_by=self.requestor,
        )

        result = check_duplicate_domain_invitation(email, self.domain)

        self.assertTrue(result)

    def test_check_duplicate_portfolio_invitation_returns_true(self):
        """check_duplicate_portfolio_invitation finds existing invitation."""
        email = "invitee@example.com"
        UserPortfolioPermission.objects.create(
            email=email,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            status=UserPortfolioPermission.Status.INVITED,
            invited_by=self.requestor,
        )

        result = check_duplicate_portfolio_invitation(email, self.portfolio)

        self.assertTrue(result)
