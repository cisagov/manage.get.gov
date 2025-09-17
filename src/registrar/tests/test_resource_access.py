from django.test import Client
from django.urls import reverse

from registrar.tests.common import (
    MockDbForIndividualTests,
    less_console_noise_decorator,
    completed_domain_request,
)
from registrar.models import (
    DomainRequest,
    Portfolio,
    UserPortfolioPermission,
    PortfolioInvitation,
)
from registrar.models.utility.portfolio_helper import (
    UserPortfolioRoleChoices,
    UserPortfolioPermissionChoices,
)
from registrar.decorators import (
    _domain_exists_under_portfolio,
    _domain_request_exists_under_portfolio,
    _member_exists_under_portfolio,
    _member_invitation_exists_under_portfolio,
)


class TestPortfolioResourceAccess(MockDbForIndividualTests):
    """Test functions that verify resources belong to a portfolio.
    More specifically, this function tests our helper utilities in decorators.py"""

    def setUp(self):
        super().setUp()

        # Create portfolios
        self.portfolio = Portfolio.objects.create(creator=self.user, organization_name="Test Portfolio")
        self.other_portfolio = Portfolio.objects.create(
            creator=self.custom_staffuser, organization_name="Other Portfolio"
        )

        # Create domain requests
        self.domain_request = completed_domain_request(name="eggnog.gov", user=self.user, portfolio=self.portfolio)

        self.other_domain_request = completed_domain_request(
            name="christmas.gov", user=self.tired_user, portfolio=self.other_portfolio
        )

        # Create domains
        self.approved_domain_request_1 = completed_domain_request(
            name="done_1.gov",
            user=self.tired_user,
            portfolio=self.portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.approved_domain_request_2 = completed_domain_request(
            name="done_2.gov",
            user=self.tired_user,
            portfolio=self.other_portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.approved_domain_request_1.approve()
        self.approved_domain_request_2.approve()
        self.domain = self.approved_domain_request_1.approved_domain
        self.other_domain = self.approved_domain_request_2.approved_domain

        # Create portfolio permissions
        self.user_permission = UserPortfolioPermission.objects.create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        self.other_user_permission = UserPortfolioPermission.objects.create(
            user=self.tired_user, portfolio=self.other_portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        # Create portfolio invitations
        self.portfolio_invitation = PortfolioInvitation.objects.create(
            email="invited@example.com",
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            status=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
        )

        self.other_portfolio_invitation = PortfolioInvitation.objects.create(
            email="other-invited@example.com",
            portfolio=self.other_portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            status=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
        )

    # Domain request tests
    @less_console_noise_decorator
    def test_domain_request_exists_under_portfolio_when_pk_is_none(self):
        """Check behavior when the PK is None."""
        self.assertTrue(_domain_request_exists_under_portfolio(self.portfolio, None))

    @less_console_noise_decorator
    def test_domain_request_exists_under_portfolio_when_exists(self):
        """Verify returns True when the domain request exists under the portfolio."""
        self.assertTrue(_domain_request_exists_under_portfolio(self.portfolio, self.domain_request.id))

    @less_console_noise_decorator
    def test_domain_request_exists_under_portfolio_when_not_exists(self):
        """Verify returns False when the domain request does not exist under the portfolio."""
        self.assertFalse(_domain_request_exists_under_portfolio(self.portfolio, self.other_domain_request.id))

    # Domain tests
    @less_console_noise_decorator
    def test_domain_exists_under_portfolio_when_pk_is_none(self):
        """Check behavior when the PK is None."""
        self.assertTrue(_domain_exists_under_portfolio(self.portfolio, None))

    @less_console_noise_decorator
    def test_domain_exists_under_portfolio_when_exists(self):
        """Verify returns True when the domain exists under the portfolio."""
        self.assertTrue(_domain_exists_under_portfolio(self.portfolio, self.domain.id))

    @less_console_noise_decorator
    def test_domain_exists_under_portfolio_when_not_exists(self):
        """Verify returns False when the domain does not exist under the portfolio."""
        self.assertFalse(_domain_exists_under_portfolio(self.portfolio, self.other_domain.id))

    # Member tests
    @less_console_noise_decorator
    def test_member_exists_under_portfolio_when_pk_is_none(self):
        """Check behavior when the PK is None."""
        self.assertTrue(_member_exists_under_portfolio(self.portfolio, None))

    @less_console_noise_decorator
    def test_member_exists_under_portfolio_when_exists(self):
        """Verify returns True when the member exists under the portfolio."""
        self.assertTrue(_member_exists_under_portfolio(self.portfolio, self.user_permission.id))

    @less_console_noise_decorator
    def test_member_exists_under_portfolio_when_not_exists(self):
        """Verify returns False when the member does not exist under the portfolio."""
        self.assertFalse(_member_exists_under_portfolio(self.portfolio, self.other_user_permission.id))

    # Member invitation tests
    @less_console_noise_decorator
    def test_member_invitation_exists_under_portfolio_when_pk_is_none(self):
        """Check behavior when the PK is None."""
        self.assertTrue(_member_invitation_exists_under_portfolio(self.portfolio, None))

    @less_console_noise_decorator
    def test_member_invitation_exists_under_portfolio_when_exists(self):
        """Verify returns True when the member invitation exists under the portfolio."""
        self.assertTrue(_member_invitation_exists_under_portfolio(self.portfolio, self.portfolio_invitation.id))

    @less_console_noise_decorator
    def test_member_invitation_exists_under_portfolio_when_not_exists(self):
        """Verify returns False when the member invitation does not exist under the portfolio."""
        self.assertFalse(_member_invitation_exists_under_portfolio(self.portfolio, self.other_portfolio_invitation.id))


class TestPortfolioDomainRequestViewAccess(MockDbForIndividualTests):
    """Tests for domain request views to ensure users can only access domain requests in their portfolio."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

        # Create portfolios
        self.portfolio = Portfolio.objects.create(creator=self.user, organization_name="Test Portfolio")
        self.other_portfolio = Portfolio.objects.create(creator=self.tired_user, organization_name="Other Portfolio")

        # Create domain requests
        self.domain_request = completed_domain_request(
            name="test-domain.gov",
            portfolio=self.portfolio,
            status=DomainRequest.DomainRequestStatus.STARTED,
            user=self.user,
        )

        self.other_domain_request = completed_domain_request(
            name="other-domain.gov",
            portfolio=self.other_portfolio,
            status=DomainRequest.DomainRequestStatus.STARTED,
            user=self.tired_user,
        )

        # Give user permission to view all requests
        self.user_permission = UserPortfolioPermission.objects.create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS],
        )

        # Setup session for portfolio views
        session = self.client.session
        session["portfolio"] = self.portfolio
        session.save()

    @less_console_noise_decorator
    def test_domain_request_view_same_portfolio(self):
        """Test that user can access domain requests in their portfolio."""
        # With just the view all permission, access should be denied
        response = self.client.get(reverse("edit-domain-request", kwargs={"domain_request_pk": self.domain_request.pk}))
        self.assertEqual(response.status_code, 403)

        # But with the edit permission, the user should be able to access this domain request
        self.user_permission.additional_permissions = [
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
            UserPortfolioPermissionChoices.EDIT_REQUESTS,
        ]
        self.user_permission.save()
        self.user_permission.refresh_from_db()
        response = self.client.get(
            reverse("edit-domain-request", kwargs={"domain_request_pk": self.domain_request.pk}), follow=True
        )
        self.assertEqual(response.status_code, 200)

    @less_console_noise_decorator
    def test_domain_request_view_different_portfolio(self):
        """Test that user cannot access domain request not in their portfolio."""
        response = self.client.get(
            reverse("edit-domain-request", kwargs={"domain_request_pk": self.other_domain_request.pk})
        )
        self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_domain_request_viewonly_same_portfolio(self):
        """Test that user can access view-only domain request in their portfolio."""
        response = self.client.get(
            reverse("domain-request-status-viewonly", kwargs={"domain_request_pk": self.domain_request.pk})
        )
        self.assertEqual(response.status_code, 200)

    @less_console_noise_decorator
    def test_domain_request_viewonly_different_portfolio(self):
        """Test that user cannot access view-only domain request not in their portfolio."""
        response = self.client.get(
            reverse("domain-request-status-viewonly", kwargs={"domain_request_pk": self.other_domain_request.pk})
        )
        self.assertEqual(response.status_code, 403)


class TestPortfolioDomainViewAccess(MockDbForIndividualTests):
    """Tests for domain views to ensure users can only access domains in their portfolio."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

        # Create portfolios
        self.portfolio = Portfolio.objects.create(creator=self.user, organization_name="Test Portfolio")
        self.other_portfolio = Portfolio.objects.create(creator=self.tired_user, organization_name="Other Portfolio")

        # Create domains through domain requests
        self.domain_request = completed_domain_request(
            name="test-domain.gov",
            portfolio=self.portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            user=self.user,
        )
        self.domain_request.approve()
        self.domain = self.domain_request.approved_domain

        self.other_domain_request = completed_domain_request(
            name="other-domain.gov",
            portfolio=self.other_portfolio,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            user=self.user,
        )
        self.other_domain_request.approve()
        self.other_domain = self.other_domain_request.approved_domain

        # Give user permission to view all domains
        self.user_permission = UserPortfolioPermission.objects.create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS],
        )

        # Setup session for portfolio views
        session = self.client.session
        session["portfolio"] = self.portfolio
        session.save()

    @less_console_noise_decorator
    def test_domain_view_same_portfolio(self):
        """Test that user can access domain in their portfolio."""
        response = self.client.get(reverse("domain", kwargs={"domain_pk": self.domain.pk}))
        self.assertEqual(response.status_code, 200)

    @less_console_noise_decorator
    def test_domain_view_different_portfolio(self):
        """Test that user cannot access domain not in their portfolio."""
        response = self.client.get(reverse("domain", kwargs={"domain_pk": self.other_domain.pk}))
        self.assertEqual(response.status_code, 403)


class TestPortfolioMemberViewAccess(MockDbForIndividualTests):
    """Tests for member views to ensure users can only access members in their portfolio."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

        # Create portfolios
        self.portfolio = Portfolio.objects.create(creator=self.user, organization_name="Test Portfolio")
        self.other_portfolio = Portfolio.objects.create(creator=self.tired_user, organization_name="Other Portfolio")

        # Create portfolio permissions
        self.member_permission = UserPortfolioPermission.objects.create(
            user=self.meoward_user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        )

        self.other_member_permission = UserPortfolioPermission.objects.create(
            user=self.lebowski_user,
            portfolio=self.other_portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )

        # Give user permission to view/edit members
        self.user_permission = UserPortfolioPermission.objects.create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        # Setup session for portfolio views
        session = self.client.session
        session["portfolio"] = self.portfolio
        session.save()

    @less_console_noise_decorator
    def test_member_view_same_portfolio(self):
        """Test that user can access member in their portfolio."""
        response = self.client.get(reverse("member", kwargs={"member_pk": self.member_permission.pk}))
        self.assertEqual(response.status_code, 200)

    @less_console_noise_decorator
    def test_member_view_different_portfolio(self):
        """Test that user cannot access member not in their portfolio."""
        response = self.client.get(reverse("member", kwargs={"member_pk": self.other_member_permission.pk}))
        self.assertEqual(response.status_code, 403)
