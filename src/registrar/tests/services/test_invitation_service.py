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


class TestInvitationService(TestCase):
    """Test suite for invitation service layer functions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username="test_invitee", email="invitee@example.com"
        )
        self.requestor = User.objects.create(
            username="test_requestor", email="requestor@example.com"
        )
        self.portfolio = Portfolio.objects.create(
            requester=self.requestor,
            organization_name="Test Organization",
            organization_type="federal",
        )
        self.domain = Domain.objects.create(name="test.gov")

    @patch(
        "registrar.services.invitation_service."
        "send_portfolio_invitation_email"
    )
    def test_invite_to_portfolio_creates_permission(self, mock_send_email):
        """invite_to_portfolio creates a UserPortfolioPermission."""
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
        self.assertEqual(permission.portfolio, self.portfolio)
        self.assertEqual(permission.roles, roles)
        self.assertEqual(
            permission.status, UserPortfolioPermission.Status.INVITED
        )
        mock_send_email.assert_called_once()

    @patch(
        "registrar.services.invitation_service." "send_domain_invitation_email"
    )
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

    @patch(
        "registrar.services.invitation_service." "send_domain_invitation_email"
    )
    def test_invite_to_domains_bulk_creates_multiple_roles(
        self, mock_send_email
    ):
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

    def test_get_pending_invitations_returns_invitations(self):
        """get_pending_invitations returns user's invitations."""
        # Create invitation
        invite_to_portfolio(
            email=self.user.email,
            portfolio=self.portfolio,
            requestor=self.requestor,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )

        result = get_pending_invitations(self.user)

        self.assertEqual(len(result["portfolio_permissions"]), 1)
        self.assertEqual(
            result["portfolio_permissions"][0].email, self.user.email
        )

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
        self.assertEqual(
            permission.status, UserPortfolioPermission.Status.ACCEPTED
        )
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
        domain_role = UserDomainRole.objects.get(
            email=email, domain=self.domain
        )
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
        permission = UserPortfolioPermission.objects.get(
            email=email, portfolio=self.portfolio
        )
        self.assertEqual(
            permission.status, UserPortfolioPermission.Status.REJECTED
        )

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
        domain_role = UserDomainRole.objects.get(
            email=email, domain=self.domain
        )
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
