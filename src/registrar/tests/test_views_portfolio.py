from django.urls import reverse
from api.tests.common import less_console_noise_decorator
from registrar.config import settings
from registrar.models import Portfolio, SeniorOfficial
from django_webtest import WebTest  # type: ignore
from registrar.models import (
    DomainRequest,
    Domain,
    DomainInformation,
    UserDomainRole,
    User,
)
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from .common import create_test_user
from waffle.testutils import override_flag
from django.contrib.sessions.middleware import SessionMiddleware

import logging

logger = logging.getLogger(__name__)


class TestPortfolio(WebTest):
    def setUp(self):
        super().setUp()
        self.user = create_test_user()
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.portfolio, _ = Portfolio.objects.get_or_create(creator=self.user, organization_name="Hotel California")
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        UserPortfolioPermission.objects.all().delete()
        Portfolio.objects.all().delete()
        UserDomainRole.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    def test_portfolio_senior_official(self):
        """Tests that the senior official page on portfolio contains the content we expect"""
        self.app.set_user(self.user.username)

        so = SeniorOfficial.objects.create(
            first_name="Saturn", last_name="Enceladus", title="Planet/Moon", email="spacedivision@igorville.com"
        )

        self.portfolio.senior_official = so
        self.portfolio.save()
        self.portfolio.refresh_from_db()

        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_PORTFOLIO],
        )

        so_portfolio_page = self.app.get(reverse("senior-official"))
        # Assert that we're on the right page
        self.assertContains(so_portfolio_page, "Senior official")
        self.assertContains(so_portfolio_page, "Saturn Enceladus")
        self.assertContains(so_portfolio_page, "Planet/Moon")
        self.assertContains(so_portfolio_page, "spacedivision@igorville.com")
        self.assertNotContains(so_portfolio_page, "Save")

        self.portfolio.delete()
        so.delete()

    @less_console_noise_decorator
    def test_middleware_does_not_redirect_if_no_permission(self):
        """Test that user with no portfolio permission is not redirected when attempting to access home"""
        self.app.set_user(self.user.username)
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, additional_permissions=[]
        )
        self.user.portfolio = self.portfolio
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home"))
            # Assert that we're on the right page
            self.assertNotContains(portfolio_page, self.portfolio.organization_name)

    @less_console_noise_decorator
    def test_middleware_does_not_redirect_if_no_portfolio(self):
        """Test that user with no assigned portfolio is not redirected when attempting to access home"""
        self.app.set_user(self.user.username)
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home"))
            # Assert that we're on the right page
            self.assertNotContains(portfolio_page, self.portfolio.organization_name)

    @less_console_noise_decorator
    def test_middleware_redirects_to_portfolio_no_domains_page(self):
        """Test that user with a portfolio and VIEW_PORTFOLIO is redirected to the no domains page"""
        self.app.set_user(self.user.username)
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_PORTFOLIO],
        )
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertContains(portfolio_page, "You aren’t managing any domains")

    @less_console_noise_decorator
    def test_middleware_redirects_to_portfolio_domains_page(self):
        """Test that user with a portfolio, VIEW_PORTFOLIO, VIEW_ALL_DOMAINS
        is redirected to portfolio domains page"""
        self.app.set_user(self.user.username)
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
            ],
        )
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, "<h1>Organization</h1>")
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')

    @less_console_noise_decorator
    def test_portfolio_domains_page_403_when_user_not_have_permission(self):
        """Test that user without proper permission is denied access to portfolio domain view"""
        self.app.set_user(self.user.username)
        UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, additional_permissions=[]
        )
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(reverse("domains"), status=403)
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_portfolio_domain_requests_page_403_when_user_not_have_permission(self):
        """Test that user without proper permission is denied access to portfolio domain view"""
        self.app.set_user(self.user.username)
        UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, additional_permissions=[]
        )
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(reverse("domain-requests"), status=403)
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_portfolio_organization_page_403_when_user_not_have_permission(self):
        """Test that user without proper permission is not allowed access to portfolio organization page"""
        self.app.set_user(self.user.username)
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, additional_permissions=[]
        )
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(reverse("organization"), status=403)
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_portfolio_organization_page_read_only(self):
        """Test that user with a portfolio can access the portfolio organization page, read only"""
        self.app.set_user(self.user.username)
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_PORTFOLIO],
        )
        self.portfolio.city = "Los Angeles"
        self.portfolio.save()
        with override_flag("organization_feature", active=True):
            response = self.app.get(reverse("organization"))
            # Assert the response is a 200
            self.assertEqual(response.status_code, 200)
            # The label for Federal agency will always be a h4
            self.assertContains(response, '<h4 class="read-only-label">Federal agency</h4>')
            # The read only label for city will be a h4
            self.assertContains(response, '<h4 class="read-only-label">City</h4>')
            self.assertNotContains(response, 'for="id_city"')
            self.assertContains(response, '<p class="read-only-value">Los Angeles</p>')

    @less_console_noise_decorator
    def test_portfolio_organization_page_edit_access(self):
        """Test that user with a portfolio can access the portfolio organization page, read only"""
        self.app.set_user(self.user.username)
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            ],
        )
        self.portfolio.city = "Los Angeles"
        self.portfolio.save()
        with override_flag("organization_feature", active=True):
            response = self.app.get(reverse("organization"))
            # Assert the response is a 200
            self.assertEqual(response.status_code, 200)
            # The label for Federal agency will always be a h4
            self.assertContains(response, '<h4 class="read-only-label">Federal agency</h4>')
            # The read only label for city will be a h4
            self.assertNotContains(response, '<h4 class="read-only-label">City</h4>')
            self.assertNotContains(response, '<p class="read-only-value">Los Angeles</p>>')
            self.assertContains(response, 'for="id_city"')

    @less_console_noise_decorator
    def test_accessible_pages_when_user_does_not_have_permission(self):
        """Tests which pages are accessible when user does not have portfolio permissions"""
        self.app.set_user(self.user.username)
        portfolio_additional_permissions = [
            UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
        ]
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, additional_permissions=portfolio_additional_permissions
        )
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, "<h1>Organization</h1>")
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertContains(portfolio_page, reverse("domains"))
            self.assertContains(portfolio_page, reverse("domain-requests"))

            # removing non-basic portfolio perms, which should remove domains
            # and domain requests from nav
            portfolio_permission.additional_permissions = [UserPortfolioPermissionChoices.VIEW_PORTFOLIO]
            portfolio_permission.save()
            portfolio_permission.refresh_from_db()

            # Members should be redirected to the readonly domains page
            portfolio_page = self.app.get(reverse("home")).follow()

            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, "<h1>Organization</h1>")
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertContains(portfolio_page, "You aren’t managing any domains")
            self.assertNotContains(portfolio_page, reverse("domains"))
            self.assertNotContains(portfolio_page, reverse("domain-requests"))

            # The organization page should still be accessible
            org_page = self.app.get(reverse("organization"))
            self.assertContains(org_page, self.portfolio.organization_name)
            self.assertContains(org_page, "<h1>Organization</h1>")

            # Both domain pages should not be accessible
            domain_page = self.app.get(reverse("domains"), expect_errors=True)
            self.assertEquals(domain_page.status_code, 403)
            domain_request_page = self.app.get(reverse("domain-requests"), expect_errors=True)
            self.assertEquals(domain_request_page.status_code, 403)

    @less_console_noise_decorator
    def test_accessible_pages_when_user_does_not_have_role(self):
        """Test that admin / memmber roles are associated with the right access"""
        self.app.set_user(self.user.username)
        portfolio_roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, roles=portfolio_roles
        )
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, "<h1>Organization</h1>")
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertContains(portfolio_page, reverse("domains"))
            self.assertContains(portfolio_page, reverse("domain-requests"))

            # removing non-basic portfolio role, which should remove domains
            # and domain requests from nav
            portfolio_permission.roles = [UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
            portfolio_permission.save()
            portfolio_permission.refresh_from_db()

            # Members should be redirected to the readonly domains page
            portfolio_page = self.app.get(reverse("home")).follow()

            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, "<h1>Organization</h1>")
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertContains(portfolio_page, "You aren’t managing any domains")
            self.assertNotContains(portfolio_page, reverse("domains"))
            self.assertNotContains(portfolio_page, reverse("domain-requests"))

            # The organization page should still be accessible
            org_page = self.app.get(reverse("organization"))
            self.assertContains(org_page, self.portfolio.organization_name)
            self.assertContains(org_page, "<h1>Organization</h1>")

            # Both domain pages should not be accessible
            domain_page = self.app.get(reverse("domains"), expect_errors=True)
            self.assertEquals(domain_page.status_code, 403)
            domain_request_page = self.app.get(reverse("domain-requests"), expect_errors=True)
            self.assertEquals(domain_request_page.status_code, 403)

    @less_console_noise_decorator
    def test_portfolio_org_name(self):
        """Can load portfolio's org name page."""
        with override_flag("organization_feature", active=True):
            self.app.set_user(self.user.username)
            portfolio_additional_permissions = [
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            ]
            portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
                user=self.user, portfolio=self.portfolio, additional_permissions=portfolio_additional_permissions
            )
            page = self.app.get(reverse("organization"))
            self.assertContains(
                page, "The name of your federal agency will be publicly listed as the domain registrant."
            )

    @less_console_noise_decorator
    def test_domain_org_name_address_content(self):
        """Org name and address information appears on the page."""
        with override_flag("organization_feature", active=True):
            self.app.set_user(self.user.username)
            portfolio_additional_permissions = [
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            ]
            portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
                user=self.user, portfolio=self.portfolio, additional_permissions=portfolio_additional_permissions
            )

            self.portfolio.organization_name = "Hotel California"
            self.portfolio.save()
            page = self.app.get(reverse("organization"))
            # Once in the sidenav, once in the main nav
            self.assertContains(page, "Hotel California", count=2)
            self.assertContains(page, "Non-Federal Agency")

    @less_console_noise_decorator
    def test_domain_org_name_address_form(self):
        """Submitting changes works on the org name address page."""
        with override_flag("organization_feature", active=True):
            self.app.set_user(self.user.username)
            portfolio_additional_permissions = [
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            ]
            portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
                user=self.user, portfolio=self.portfolio, additional_permissions=portfolio_additional_permissions
            )

            self.portfolio.address_line1 = "1600 Penn Ave"
            self.portfolio.save()
            portfolio_org_name_page = self.app.get(reverse("organization"))
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

            portfolio_org_name_page.form["address_line1"] = "6 Downing st"
            portfolio_org_name_page.form["city"] = "London"

            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            success_result_page = portfolio_org_name_page.form.submit()
            self.assertEqual(success_result_page.status_code, 200)

            self.assertContains(success_result_page, "6 Downing st")
            self.assertContains(success_result_page, "London")

    @less_console_noise_decorator
    def test_portfolio_in_session_when_organization_feature_active(self):
        """When organization_feature flag is true and user has a portfolio,
        the portfolio should be set in session."""
        self.client.force_login(self.user)
        portfolio_roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=portfolio_roles)
        with override_flag("organization_feature", active=True):
            response = self.client.get(reverse("home"))
            # Ensure that middleware processes the session
            session_middleware = SessionMiddleware(lambda request: None)
            session_middleware.process_request(response.wsgi_request)
            response.wsgi_request.session.save()
            # Access the session via the request
            session = response.wsgi_request.session
            # Check if the 'portfolio' session variable exists
            self.assertIn("portfolio", session, "Portfolio session variable should exist.")
            # Check the value of the 'portfolio' session variable
            self.assertEqual(session["portfolio"], self.portfolio, "Portfolio session variable has the wrong value.")

    @less_console_noise_decorator
    def test_portfolio_in_session_is_none_when_organization_feature_inactive(self):
        """When organization_feature flag is false and user has a portfolio,
        the portfolio should be set to None in session.
        This test also satisfies the condition when multiple_portfolios flag
        is false and user has a portfolio, so won't add a redundant test for that."""
        self.client.force_login(self.user)
        portfolio_roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=portfolio_roles)
        response = self.client.get(reverse("home"))
        # Ensure that middleware processes the session
        session_middleware = SessionMiddleware(lambda request: None)
        session_middleware.process_request(response.wsgi_request)
        response.wsgi_request.session.save()
        # Access the session via the request
        session = response.wsgi_request.session
        # Check if the 'portfolio' session variable exists
        self.assertIn("portfolio", session, "Portfolio session variable should exist.")
        # Check the value of the 'portfolio' session variable
        self.assertIsNone(session["portfolio"])

    @less_console_noise_decorator
    def test_portfolio_in_session_is_none_when_organization_feature_active_and_no_portfolio(self):
        """When organization_feature flag is true and user does not have a portfolio,
        the portfolio should be set to None in session."""
        self.client.force_login(self.user)
        with override_flag("organization_feature", active=True):
            response = self.client.get(reverse("home"))
            # Ensure that middleware processes the session
            session_middleware = SessionMiddleware(lambda request: None)
            session_middleware.process_request(response.wsgi_request)
            response.wsgi_request.session.save()
            # Access the session via the request
            session = response.wsgi_request.session
            # Check if the 'portfolio' session variable exists
            self.assertIn("portfolio", session, "Portfolio session variable should exist.")
            # Check the value of the 'portfolio' session variable
            self.assertIsNone(session["portfolio"])

    @less_console_noise_decorator
    def test_portfolio_in_session_when_multiple_portfolios_active(self):
        """When multiple_portfolios flag is true and user has a portfolio,
        the portfolio should be set in session."""
        self.client.force_login(self.user)
        portfolio_roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=portfolio_roles)
        with override_flag("organization_feature", active=True), override_flag("multiple_portfolios", active=True):
            response = self.client.get(reverse("home"))
            # Ensure that middleware processes the session
            session_middleware = SessionMiddleware(lambda request: None)
            session_middleware.process_request(response.wsgi_request)
            response.wsgi_request.session.save()
            # Access the session via the request
            session = response.wsgi_request.session
            # Check if the 'portfolio' session variable exists
            self.assertIn("portfolio", session, "Portfolio session variable should exist.")
            # Check the value of the 'portfolio' session variable
            self.assertEqual(session["portfolio"], self.portfolio, "Portfolio session variable has the wrong value.")

    @less_console_noise_decorator
    def test_portfolio_in_session_is_none_when_multiple_portfolios_active_and_no_portfolio(self):
        """When multiple_portfolios flag is true and user does not have a portfolio,
        the portfolio should be set to None in session."""
        self.client.force_login(self.user)
        with override_flag("multiple_portfolios", active=True):
            response = self.client.get(reverse("home"))
            # Ensure that middleware processes the session
            session_middleware = SessionMiddleware(lambda request: None)
            session_middleware.process_request(response.wsgi_request)
            response.wsgi_request.session.save()
            # Access the session via the request
            session = response.wsgi_request.session
            # Check if the 'portfolio' session variable exists
            self.assertIn("portfolio", session, "Portfolio session variable should exist.")
            # Check the value of the 'portfolio' session variable
            self.assertIsNone(session["portfolio"])

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    def test_org_member_can_only_see_domains_with_appropriate_permissions(self):
        """A user with the role organization_member should not have access to the domains page
        if they do not have the right permissions.
        """

        permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        )

        # A default organization member should not be able to see any domains
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"), follow=True)

        self.assertFalse(self.user.has_domains_portfolio_permission(response.wsgi_request.session.get("portfolio")))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You aren")

        # Test the domains page - this user should not have access
        response = self.client.get(reverse("domains"))
        self.assertEqual(response.status_code, 403)

        # Ensure that this user can see domains with the right permissions
        permission.additional_permissions = [UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS]
        permission.save()
        permission.refresh_from_db()

        # Test the domains page - this user should have access
        response = self.client.get(reverse("domains"))
        self.assertTrue(self.user.has_domains_portfolio_permission(response.wsgi_request.session.get("portfolio")))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Domain name")

        # Test the managed domains permission
        permission.additional_permissions = [UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS]
        permission.save()
        permission.refresh_from_db()

        # Test the domains page - this user should have access
        response = self.client.get(reverse("domains"))
        self.assertTrue(self.user.has_domains_portfolio_permission(response.wsgi_request.session.get("portfolio")))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Domain name")
        permission.delete()
