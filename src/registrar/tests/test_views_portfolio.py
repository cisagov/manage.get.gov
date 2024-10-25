from django.urls import reverse
from api.tests.common import less_console_noise_decorator
from registrar.config import settings
from registrar.models import Portfolio, SeniorOfficial
from unittest.mock import MagicMock
from django_webtest import WebTest  # type: ignore
from registrar.models import (
    DomainRequest,
    Domain,
    DomainInformation,
    UserDomainRole,
    User,
    Suborganization,
    AllowedEmail,
)
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_group import UserGroup
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from .common import MockSESClient, completed_domain_request, create_test_user, create_user
from waffle.testutils import override_flag
from django.contrib.sessions.middleware import SessionMiddleware
import boto3_mocking  # type: ignore
from django.test import Client
import logging

logger = logging.getLogger(__name__)


class TestPortfolio(WebTest):
    def setUp(self):
        super().setUp()
        self.client = Client()
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
        UserPortfolioPermission.objects.get_or_create(
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
            self.assertContains(response, '<h4 class="read-only-label">Organization name</h4>')
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
            self.assertContains(response, '<h4 class="read-only-label">Organization name</h4>')
            # The read only label for city will be a h4
            self.assertNotContains(response, '<h4 class="read-only-label">City</h4>')
            self.assertNotContains(response, '<p class="read-only-value">Los Angeles</p>')
            self.assertContains(response, 'for="id_city"')

    @less_console_noise_decorator
    @override_flag("organization_requests", active=True)
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
    @override_flag("organization_requests", active=True)
    def test_accessible_pages_when_user_does_not_have_role(self):
        """Test that admin / memmber roles are associated with the right access"""
        self.app.set_user(self.user.username)
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, roles=roles
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
            self.assertContains(page, "The name of your organization will be publicly listed as the domain registrant.")

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
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=roles)
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
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=roles)
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
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=roles)
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

        self.assertFalse(self.user.has_any_domains_portfolio_permission(response.wsgi_request.session.get("portfolio")))
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
        self.assertTrue(self.user.has_any_domains_portfolio_permission(response.wsgi_request.session.get("portfolio")))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Domain name")

        # Test the managed domains permission
        permission.additional_permissions = [UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS]
        permission.save()
        permission.refresh_from_db()

        # Test the domains page - this user should have access
        response = self.client.get(reverse("domains"))
        self.assertTrue(self.user.has_any_domains_portfolio_permission(response.wsgi_request.session.get("portfolio")))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Domain name")
        permission.delete()

    def check_widescreen_is_loaded(self, page_to_check):
        """Tests if class modifiers for widescreen mode are appropriately loaded into the DOM
        for the given page"""

        self.client.force_login(self.user)

        # Ensure that this user can see domains with the right permissions
        permission, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        )
        permission.additional_permissions = [UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS]
        permission.save()
        permission.refresh_from_db()

        response = self.client.get(reverse(page_to_check))
        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for widescreen modifier
        self.assertContains(response, "--widescreen")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    def test_widescreen_css_org_model(self):
        """Tests if class modifiers for widescreen mode are appropriately
        loaded into the DOM for org model pages"""
        self.check_widescreen_is_loaded("domains")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=False)
    def test_widescreen_css_non_org_model(self):
        """Tests if class modifiers for widescreen mode are appropriately
        loaded into the DOM for non-org model pages"""
        self.check_widescreen_is_loaded("home")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=False)
    def test_organization_requests_waffle_flag_off_hides_nav_link_and_restricts_permission(self):
        """Setting the organization_requests waffle off hides the nav link and restricts access to the requests page"""
        self.app.set_user(self.user.username)

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
                UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
            ],
        )

        home = self.app.get(reverse("home")).follow()

        self.assertContains(home, "Hotel California")
        self.assertNotContains(home, "Domain requests")

        domain_requests = self.app.get(reverse("domain-requests"), expect_errors=True)
        self.assertEqual(domain_requests.status_code, 403)

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_organization_requests_waffle_flag_on_shows_nav_link_and_allows_permission(self):
        """Setting the organization_requests waffle on shows the nav link and allows access to the requests page"""
        self.app.set_user(self.user.username)

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
                UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
            ],
        )

        home = self.app.get(reverse("home")).follow()

        self.assertContains(home, "Hotel California")
        self.assertContains(home, "Domain requests")

        domain_requests = self.app.get(reverse("domain-requests"))
        self.assertEqual(domain_requests.status_code, 200)

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=False)
    def test_organization_members_waffle_flag_off_hides_nav_link(self):
        """Setting the organization_members waffle off hides the nav link"""
        self.app.set_user(self.user.username)

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
                UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
            ],
        )

        home = self.app.get(reverse("home")).follow()

        self.assertContains(home, "Hotel California")
        self.assertNotContains(home, "Members")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_organization_members_waffle_flag_on_shows_nav_link(self):
        """Setting the organization_members waffle on shows the nav link"""
        self.app.set_user(self.user.username)

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
            ],
        )

        home = self.app.get(reverse("home")).follow()

        self.assertContains(home, "Hotel California")
        self.assertContains(home, "Members")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_cannot_view_members_table(self):
        """Test that user without proper permission is denied access to members view"""

        # Users can only view the members table if they have
        # Portfolio Permission "view_members" selected.
        # NOTE: Admins, by default, do NOT have permission
        # to view/edit members.  This must be enabled explicitly
        # in the "additional permissions" section for a portfolio
        # permission.
        #
        # Scenarios to test include;
        # (1) - User is not admin and can view portfolio, but not the members table
        # (1) - User is admin and can view portfolio, but not the members table

        # --- non-admin
        self.app.set_user(self.user.username)

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            ],
        )
        # Verify that the user cannot access the members page
        # This will redirect the user to the members page.
        self.client.force_login(self.user)
        response = self.client.get(reverse("members"), follow=True)
        # Assert the response is a 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # --- admin
        UserPortfolioPermission.objects.filter(user=self.user, portfolio=self.portfolio).update(
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        # Verify that the user cannot access the members page
        # This will redirect the user to the members page.
        response = self.client.get(reverse("members"), follow=True)
        # Assert the response is a 403 Forbidden
        self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_can_view_members_table(self):
        """Test that user with proper permission is able to access members view"""

        self.app.set_user(self.user.username)

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
            ],
        )

        # Verify that the user can access the members page
        # This will redirect the user to the members page.
        self.client.force_login(self.user)
        response = self.client.get(reverse("members"), follow=True)
        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)

        # ---- Useful debugging stub to see what "assertContains" is finding
        # pattern = r'Members'
        # matches = re.findall(pattern, response.content.decode('utf-8'))
        # for match in matches:
        #     TerminalHelper.colorful_logger(logger.info, TerminalColors.OKCYAN, f"{match}")

        # Make sure the page loaded
        self.assertContains(response, "Members")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_can_manage_members(self):
        """Test that user with proper permission is able to manage members"""
        user = self.user
        self.app.set_user(user.username)

        # give user permissions to view AND manage members
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
                UserPortfolioPermissionChoices.EDIT_MEMBERS,
            ],
        )

        # Give user permissions to modify user objects in the DB
        group, _ = UserGroup.objects.get_or_create(name="full_access_group")
        # Add the user to the group
        user.groups.set([group])

        # Verify that the user can access the members page
        # This will redirect the user to the members page.
        self.client.force_login(self.user)
        response = self.client.get(reverse("members"), follow=True)
        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)

        # Verify that manage settings are sent in the dynamic HTML
        self.client.force_login(self.user)
        response = self.client.get(reverse("get_portfolio_members_json") + f"?portfolio={self.portfolio.pk}")
        self.assertContains(response, '"action_label": "Manage"')
        self.assertContains(response, '"svg_icon": "settings"')

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_view_only_members(self):
        """Test that user with view only permission settings can only
        view members (not manage them)"""
        user = self.user
        self.app.set_user(user.username)

        # give user permissions to view AND manage members
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
            ],
        )
        # Give user permissions to modify user objects in the DB
        group, _ = UserGroup.objects.get_or_create(name="full_access_group")
        # Add the user to the group
        user.groups.set([group])

        # Verify that the user can access the members page
        # This will redirect the user to the members page.
        self.client.force_login(self.user)
        response = self.client.get(reverse("members"), follow=True)
        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)

        # Verify that view-only settings are sent in the dynamic HTML
        response = self.client.get(reverse("get_portfolio_members_json") + f"?portfolio={self.portfolio.pk}")
        self.assertContains(response, '"action_label": "View"')
        self.assertContains(response, '"svg_icon": "visibility"')

    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_members_admin_detection(self):
        """Test that user with proper permission is able to manage members"""
        user = self.user
        self.app.set_user(user.username)

        # give user permissions to view AND manage members
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
                UserPortfolioPermissionChoices.EDIT_MEMBERS,
            ],
        )

        # Give user permissions to modify user objects in the DB
        group, _ = UserGroup.objects.get_or_create(name="full_access_group")
        # Add the user to the group
        user.groups.set([group])

        # Verify that the user can access the members page
        # This will redirect the user to the members page.
        self.client.force_login(self.user)
        response = self.client.get(reverse("members"), follow=True)
        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)
        # Verify that admin info is sent in the dynamic HTML
        response = self.client.get(reverse("get_portfolio_members_json") + f"?portfolio={self.portfolio.pk}")
        # TerminalHelper.colorful_logger(logger.info, TerminalColors.OKCYAN, f"{response.content}")
        self.assertContains(response, '"is_admin": true')

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    def test_cannot_view_member_page_when_flag_is_off(self):
        """Test that user cannot access the member page when waffle flag is off"""

        # Verify that the user cannot access the member page
        self.client.force_login(self.user)
        response = self.client.get(reverse("member", kwargs={"pk": 1}), follow=True)
        # Make sure the page is denied
        self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_cannot_view_member_page_when_user_has_no_permission(self):
        """Test that user cannot access the member page without proper permission"""

        # give user base permissions
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )

        # Verify that the user cannot access the member page
        self.client.force_login(self.user)
        response = self.client.get(reverse("member", kwargs={"pk": 1}), follow=True)
        # Make sure the page is denied
        self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_can_view_member_page_when_user_has_view_members(self):
        """Test that user can access the member page with view_members permission"""

        # Arrange
        # give user permissions to view members
        permission_obj, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
            ],
        )

        # Verify the page can be accessed
        self.client.force_login(self.user)
        response = self.client.get(reverse("member", kwargs={"pk": permission_obj.pk}), follow=True)
        self.assertEqual(response.status_code, 200)

        # Assert text within the page is correct
        self.assertContains(response, "First Last")
        self.assertContains(response, self.user.email)
        self.assertContains(response, "Basic access")
        self.assertContains(response, "No access")
        self.assertContains(response, "View all members")
        self.assertContains(response, "This member does not manage any domains.")

        # Assert buttons and links within the page are correct
        self.assertNotContains(response, "usa-button--more-actions")  # test that 3 dot is not present
        self.assertNotContains(response, "sprite.svg#edit")  # test that Edit link is not present
        self.assertNotContains(response, "sprite.svg#settings")  # test that Manage link is not present
        self.assertContains(response, "sprite.svg#visibility")  # test that View link is present

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_can_view_member_page_when_user_has_edit_members(self):
        """Test that user can access the member page with edit_members permission"""

        # Arrange
        # give user permissions to view AND manage members
        permission_obj, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.EDIT_MEMBERS,
            ],
        )

        # Verify the page can be accessed
        self.client.force_login(self.user)
        response = self.client.get(reverse("member", kwargs={"pk": permission_obj.pk}), follow=True)
        self.assertEqual(response.status_code, 200)

        # Assert text within the page is correct
        self.assertContains(response, "First Last")
        self.assertContains(response, self.user.email)
        self.assertContains(response, "Admin access")
        self.assertContains(response, "View all requests plus create requests")
        self.assertContains(response, "View all members plus manage members")
        self.assertContains(
            response, 'This member does not manage any domains. To assign this member a domain, click "Manage"'
        )

        # Assert buttons and links within the page are correct
        self.assertContains(response, "usa-button--more-actions")  # test that 3 dot is present
        self.assertContains(response, "sprite.svg#edit")  # test that Edit link is present
        self.assertContains(response, "sprite.svg#settings")  # test that Manage link is present
        self.assertNotContains(response, "sprite.svg#visibility")  # test that View link is not present

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    def test_cannot_view_invitedmember_page_when_flag_is_off(self):
        """Test that user cannot access the invitedmember page when waffle flag is off"""

        # Verify that the user cannot access the member page
        self.client.force_login(self.user)
        response = self.client.get(reverse("invitedmember", kwargs={"pk": 1}), follow=True)
        # Make sure the page is denied
        self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_cannot_view_invitedmember_page_when_user_has_no_permission(self):
        """Test that user cannot access the invitedmember page without proper permission"""

        # give user base permissions
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )

        # Verify that the user cannot access the member page
        self.client.force_login(self.user)
        response = self.client.get(reverse("invitedmember", kwargs={"pk": 1}), follow=True)
        # Make sure the page is denied
        self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_can_view_invitedmember_page_when_user_has_view_members(self):
        """Test that user can access the invitedmember page with view_members permission"""

        # Arrange
        # give user permissions to view members
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
            ],
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(
            email="info@example.com",
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
            ],
        )

        # Verify the page can be accessed
        self.client.force_login(self.user)
        response = self.client.get(reverse("invitedmember", kwargs={"pk": portfolio_invitation.pk}), follow=True)
        self.assertEqual(response.status_code, 200)

        # Assert text within the page is correct
        self.assertContains(response, "Invited")
        self.assertContains(response, portfolio_invitation.email)
        self.assertContains(response, "Basic access")
        self.assertContains(response, "No access")
        self.assertContains(response, "View all members")
        self.assertContains(response, "This member does not manage any domains.")

        # Assert buttons and links within the page are correct
        self.assertNotContains(response, "usa-button--more-actions")  # test that 3 dot is not present
        self.assertNotContains(response, "sprite.svg#edit")  # test that Edit link is not present
        self.assertNotContains(response, "sprite.svg#settings")  # test that Manage link is not present
        self.assertContains(response, "sprite.svg#visibility")  # test that View link is present

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_members", active=True)
    def test_can_view_invitedmember_page_when_user_has_edit_members(self):
        """Test that user can access the invitedmember page with edit_members permission"""

        # Arrange
        # give user permissions to view AND manage members
        permission_obj, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.EDIT_MEMBERS,
            ],
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(
            email="info@example.com",
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.EDIT_MEMBERS,
            ],
        )

        # Verify the page can be accessed
        self.client.force_login(self.user)
        response = self.client.get(reverse("invitedmember", kwargs={"pk": portfolio_invitation.pk}), follow=True)
        self.assertEqual(response.status_code, 200)

        # Assert text within the page is correct
        self.assertContains(response, "Invited")
        self.assertContains(response, portfolio_invitation.email)
        self.assertContains(response, "Admin access")
        self.assertContains(response, "View all requests plus create requests")
        self.assertContains(response, "View all members plus manage members")
        self.assertContains(
            response, 'This member does not manage any domains. To assign this member a domain, click "Manage"'
        )

        # Assert buttons and links within the page are correct
        self.assertContains(response, "usa-button--more-actions")  # test that 3 dot is present
        self.assertContains(response, "sprite.svg#edit")  # test that Edit link is present
        self.assertContains(response, "sprite.svg#settings")  # test that Manage link is present
        self.assertNotContains(response, "sprite.svg#visibility")  # test that View link is not present

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    def test_portfolio_domain_requests_page_when_user_has_no_permissions(self):
        """Test the no requests page"""
        UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        )
        self.client.force_login(self.user)
        # create and submit a domain request
        domain_request = completed_domain_request(user=self.user)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            domain_request.submit()
            domain_request.save()

        requests_page = self.client.get(reverse("no-portfolio-requests"), follow=True)

        self.assertContains(requests_page, "You don’t have access to domain requests.")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_main_nav_when_user_has_no_permissions(self):
        """Test the nav contains a link to the no requests page"""
        UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        )
        self.client.force_login(self.user)
        # create and submit a domain request
        domain_request = completed_domain_request(user=self.user)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            domain_request.submit()
            domain_request.save()

        portfolio_landing_page = self.client.get(reverse("home"), follow=True)

        # link to no requests
        self.assertContains(portfolio_landing_page, "no-organization-requests/")
        # dropdown
        self.assertNotContains(portfolio_landing_page, "basic-nav-section-two")
        # link to requests
        self.assertNotContains(portfolio_landing_page, 'href="/requests/')
        # link to create
        self.assertNotContains(portfolio_landing_page, 'href="/request/')

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_main_nav_when_user_has_all_permissions(self):
        """Test the nav contains a dropdown with a link to create and another link to view requests
        Also test for the existence of the Create a new request btn on the requests page"""
        UserPortfolioPermission.objects.get_or_create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        self.client.force_login(self.user)
        # create and submit a domain request
        domain_request = completed_domain_request(user=self.user)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            domain_request.submit()
            domain_request.save()

        portfolio_landing_page = self.client.get(reverse("home"), follow=True)

        # link to no requests
        self.assertNotContains(portfolio_landing_page, "no-organization-requests/")
        # dropdown
        self.assertContains(portfolio_landing_page, "basic-nav-section-two")
        # link to requests
        self.assertContains(portfolio_landing_page, 'href="/requests/')
        # link to create
        self.assertContains(portfolio_landing_page, 'href="/request/')

        requests_page = self.client.get(reverse("domain-requests"))

        # create new request btn
        self.assertContains(requests_page, "Start a new domain request")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_main_nav_when_user_has_view_but_not_edit_permissions(self):
        """Test the nav contains a simple link to view requests
        Also test for the existence of the Create a new request btn on the requests page"""
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
            ],
        )
        self.client.force_login(self.user)
        # create and submit a domain request
        domain_request = completed_domain_request(user=self.user)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            domain_request.submit()
            domain_request.save()

        portfolio_landing_page = self.client.get(reverse("home"), follow=True)

        # link to no requests
        self.assertNotContains(portfolio_landing_page, "no-organization-requests/")
        # dropdown
        self.assertNotContains(portfolio_landing_page, "basic-nav-section-two")
        # link to requests
        self.assertContains(portfolio_landing_page, 'href="/requests/')
        # link to create
        self.assertNotContains(portfolio_landing_page, 'href="/request/')

        requests_page = self.client.get(reverse("domain-requests"))

        # create new request btn
        self.assertNotContains(requests_page, "Start a new domain request")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_organization_requests_additional_column(self):
        """The requests table has a column for created at"""
        self.app.set_user(self.user.username)

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
                UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
            ],
        )

        home = self.app.get(reverse("home")).follow()

        self.assertContains(home, "Hotel California")
        self.assertContains(home, "Domain requests")

        domain_requests = self.app.get(reverse("domain-requests"))
        self.assertEqual(domain_requests.status_code, 200)

        self.assertContains(domain_requests, "Created by")

    @less_console_noise_decorator
    def test_no_org_requests_no_additional_column(self):
        """The requests table does not have a column for created at"""
        self.app.set_user(self.user.username)

        home = self.app.get(reverse("home"))

        self.assertContains(home, "Domain requests")
        self.assertNotContains(home, "Created by")

    @less_console_noise_decorator
    def test_portfolio_cache_updates_when_modified(self):
        """Test that the portfolio in session updates when the portfolio is modified"""
        self.client.force_login(self.user)
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=roles)

        with override_flag("organization_feature", active=True):
            # Initial request to set the portfolio in session
            response = self.client.get(reverse("home"), follow=True)

            portfolio = self.client.session.get("portfolio")
            self.assertEqual(portfolio.organization_name, "Hotel California")
            self.assertContains(response, "Hotel California")

            # Modify the portfolio
            self.portfolio.organization_name = "Updated Hotel California"
            self.portfolio.save()

            # Make another request
            response = self.client.get(reverse("home"), follow=True)

            # Check if the updated portfolio name is in the response
            self.assertContains(response, "Updated Hotel California")

            # Verify that the session contains the updated portfolio
            portfolio = self.client.session.get("portfolio")
            self.assertEqual(portfolio.organization_name, "Updated Hotel California")

    @less_console_noise_decorator
    def test_portfolio_cache_updates_when_flag_disabled_while_logged_in(self):
        """Test that the portfolio in session is set to None when the organization_feature flag is disabled"""
        self.client.force_login(self.user)
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio, roles=roles)

        with override_flag("organization_feature", active=True):
            # Initial request to set the portfolio in session
            response = self.client.get(reverse("home"), follow=True)
            portfolio = self.client.session.get("portfolio")
            self.assertEqual(portfolio.organization_name, "Hotel California")
            self.assertContains(response, "Hotel California")

        # Disable the organization_feature flag
        with override_flag("organization_feature", active=False):
            # Make another request
            response = self.client.get(reverse("home"))
            self.assertIsNone(self.client.session.get("portfolio"))
            self.assertNotContains(response, "Hotel California")

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_org_user_can_delete_own_domain_request_with_permission(self):
        """Test that an org user with edit permission can delete their own DomainRequest with a deletable status."""

        # Assign the user to a portfolio with edit permission
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.EDIT_REQUESTS],
        )

        # Create a domain request with status WITHDRAWN
        domain_request = completed_domain_request(
            name="test-domain.gov",
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            portfolio=self.portfolio,
        )
        domain_request.creator = self.user
        domain_request.save()

        self.client.force_login(self.user)
        # Perform delete
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        # Check that the response is 200
        self.assertEqual(response.status_code, 200)

        # Check that the domain request no longer exists
        self.assertFalse(DomainRequest.objects.filter(pk=domain_request.pk).exists())
        domain_request.delete()

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_delete_domain_request_as_org_user_without_permission_with_deletable_status(self):
        """Test that an org user without edit permission cant delete their DomainRequest even if status is deletable."""

        # Assign the user to a portfolio without edit permission
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[],
        )

        # Create a domain request with status STARTED
        domain_request = completed_domain_request(
            name="test-domain.gov",
            status=DomainRequest.DomainRequestStatus.STARTED,
            portfolio=self.portfolio,
        )
        domain_request.creator = self.user
        domain_request.save()

        self.client.force_login(self.user)
        # Attempt to delete
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        # Check response is 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Check that the domain request still exists
        self.assertTrue(DomainRequest.objects.filter(pk=domain_request.pk).exists())
        domain_request.delete()

    @less_console_noise_decorator
    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    def test_org_user_cannot_delete_others_domain_requests(self):
        """Test that an org user with edit permission cannot delete DomainRequests they did not create."""

        # Assign the user to a portfolio with edit permission
        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.EDIT_REQUESTS],
        )

        # Create another user and a domain request
        other_user = User.objects.create(username="other_user")
        domain_request = completed_domain_request(
            name="test-domain.gov",
            status=DomainRequest.DomainRequestStatus.STARTED,
            portfolio=self.portfolio,
        )
        domain_request.creator = other_user
        domain_request.save()

        self.client.force_login(self.user)
        # Perform delete as self.user
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        # Check response is 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Check that the domain request still exists
        self.assertTrue(DomainRequest.objects.filter(pk=domain_request.pk).exists())
        domain_request.delete()


class TestRequestingEntity(WebTest):
    """The requesting entity page is a domain request form that only exists
    within the context of a portfolio."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.user = create_user()
        self.portfolio, _ = Portfolio.objects.get_or_create(creator=self.user, organization_name="Hotel California")
        self.portfolio_2, _ = Portfolio.objects.get_or_create(creator=self.user, organization_name="Hotel Alaska")
        self.suborganization, _ = Suborganization.objects.get_or_create(
            name="Rocky road",
            portfolio=self.portfolio,
        )
        self.suborganization_2, _ = Suborganization.objects.get_or_create(
            name="Vanilla",
            portfolio=self.portfolio,
        )
        self.unrelated_suborganization, _ = Suborganization.objects.get_or_create(
            name="Cold",
            portfolio=self.portfolio_2,
        )
        self.portfolio_role = UserPortfolioPermission.objects.create(
            portfolio=self.portfolio, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        # Login the current user
        self.app.set_user(self.user.username)

        self.mock_client_class = MagicMock()
        self.mock_client = self.mock_client_class.return_value

    def tearDown(self):
        UserDomainRole.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        Suborganization.objects.all().delete()
        Portfolio.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @less_console_noise_decorator
    def test_requesting_entity_page_new_request(self):
        """Tests that the requesting entity page loads correctly when a new request is started"""

        response = self.app.get(reverse("domain-request:"))

        # Navigate past the intro page
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_form = response.forms[0]
        response = intro_form.submit().follow()

        # Test the requesting entiy page
        self.assertContains(response, "Who will use the domain you’re requesting?")
        self.assertContains(response, "Add suborganization information")
        # We expect to see the portfolio name in two places:
        # the header, and as one of the radio button options.
        self.assertContains(response, self.portfolio.organization_name, count=2)

        # We expect the dropdown list to contain the suborganizations that currently exist on this portfolio
        self.assertContains(response, self.suborganization.name, count=1)
        self.assertContains(response, self.suborganization_2.name, count=1)

        # However, we should only see suborgs that are on the actual portfolio
        self.assertNotContains(response, self.unrelated_suborganization.name)

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @less_console_noise_decorator
    def test_requesting_entity_page_existing_suborg_submission(self):
        """Tests that you can submit a form on this page and set a suborg"""
        response = self.app.get(reverse("domain-request:"))

        # Navigate past the intro page
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        form = response.forms[0]
        response = form.submit().follow()

        # Check that we're on the right page
        self.assertContains(response, "Who will use the domain you’re requesting?")
        form = response.forms[0]

        # Test selecting an existing suborg
        form["portfolio_requesting_entity-is_suborganization"] = True
        form["portfolio_requesting_entity-sub_organization"] = f"{self.suborganization.id}"
        form["portfolio_requesting_entity-is_custom_suborganization"] = False

        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        response = form.submit().follow()

        # Ensure that the post occurred successfully by checking that we're on the following page.
        self.assertContains(response, "Current websites")
        created_domain_request_exists = DomainRequest.objects.filter(
            organization_name__isnull=True, sub_organization=self.suborganization
        ).exists()
        self.assertTrue(created_domain_request_exists)

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @less_console_noise_decorator
    def test_requesting_entity_page_new_suborg_submission(self):
        """Tests that you can submit a form on this page and set a new suborg"""
        response = self.app.get(reverse("domain-request:"))

        # Navigate past the intro page
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        form = response.forms[0]
        response = form.submit().follow()

        # Check that we're on the right page
        self.assertContains(response, "Who will use the domain you’re requesting?")
        form = response.forms[0]

        # Test selecting an existing suborg
        form["portfolio_requesting_entity-is_suborganization"] = True
        form["portfolio_requesting_entity-is_custom_suborganization"] = True
        form["portfolio_requesting_entity-sub_organization"] = ""

        form["portfolio_requesting_entity-requested_suborganization"] = "moon"
        form["portfolio_requesting_entity-suborganization_city"] = "kepler"
        form["portfolio_requesting_entity-suborganization_state_territory"] = "AL"

        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        response = form.submit().follow()

        # Ensure that the post occurred successfully by checking that we're on the following page.
        self.assertContains(response, "Current websites")
        created_domain_request_exists = DomainRequest.objects.filter(
            organization_name__isnull=True,
            sub_organization__isnull=True,
            requested_suborganization="moon",
            suborganization_city="kepler",
            suborganization_state_territory=DomainRequest.StateTerritoryChoices.ALABAMA,
        ).exists()
        self.assertTrue(created_domain_request_exists)

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @less_console_noise_decorator
    def test_requesting_entity_page_organization_submission(self):
        """Tests submitting an organization on the requesting org form"""
        response = self.app.get(reverse("domain-request:"))

        # Navigate past the intro page
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        form = response.forms[0]
        response = form.submit().follow()

        # Check that we're on the right page
        self.assertContains(response, "Who will use the domain you’re requesting?")
        form = response.forms[0]

        # Test selecting an existing suborg
        form["portfolio_requesting_entity-is_suborganization"] = False

        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        response = form.submit().follow()

        # Ensure that the post occurred successfully by checking that we're on the following page.
        self.assertContains(response, "Current websites")
        created_domain_request_exists = DomainRequest.objects.filter(
            organization_name=self.portfolio.organization_name,
        ).exists()
        self.assertTrue(created_domain_request_exists)

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @less_console_noise_decorator
    def test_requesting_entity_page_errors(self):
        """Tests that we get the expected form errors on requesting entity"""
        domain_request = completed_domain_request(user=self.user, portfolio=self.portfolio)
        response = self.app.get(reverse("edit-domain-request", kwargs={"id": domain_request.pk})).follow()
        form = response.forms[0]
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Test missing suborganization selection
        form["portfolio_requesting_entity-is_suborganization"] = True
        form["portfolio_requesting_entity-sub_organization"] = ""

        response = form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        self.assertContains(response, "Select a suborganization.", status_code=200)

        # Test missing custom suborganization details
        form["portfolio_requesting_entity-is_custom_suborganization"] = True
        response = form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        self.assertContains(response, "Enter details for your organization name.", status_code=200)
        self.assertContains(response, "Enter details for your city.", status_code=200)
        self.assertContains(response, "Enter details for your state or territory.", status_code=200)

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_requesting_entity_submission_email_sent(self):
        """Tests that an email is sent out on successful form submission"""
        AllowedEmail.objects.create(email=self.user.email)
        domain_request = completed_domain_request(
            user=self.user,
            # This is the additional details field
            has_anything_else=True,
        )
        domain_request.portfolio = self.portfolio
        domain_request.requested_suborganization = "moon"
        domain_request.suborganization_city = "kepler"
        domain_request.suborganization_state_territory = DomainRequest.StateTerritoryChoices.ALABAMA
        domain_request.save()
        domain_request.refresh_from_db()

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client_class):
            domain_request.submit()
        _, kwargs = self.mock_client.send_email.call_args
        body = kwargs["Content"]["Simple"]["Body"]["Text"]["Data"]

        self.assertNotIn("Anything else", body)
        self.assertIn("kepler, AL", body)
        self.assertIn("Requesting entity:", body)
        self.assertIn("Administrators from your organization:", body)

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_requesting_entity_viewonly(self):
        """Tests the review steps page on under our viewonly context"""
        domain_request = completed_domain_request(
            user=create_test_user(),
            # This is the additional details field
            has_anything_else=True,
        )
        domain_request.portfolio = self.portfolio
        domain_request.requested_suborganization = "moon"
        domain_request.suborganization_city = "kepler"
        domain_request.suborganization_state_territory = DomainRequest.StateTerritoryChoices.ALABAMA
        domain_request.save()
        domain_request.refresh_from_db()

        domain_request.submit()

        response = self.app.get(reverse("domain-request-status-viewonly", kwargs={"pk": domain_request.pk}))
        self.assertContains(response, "Requesting entity")
        self.assertContains(response, "moon")
        self.assertContains(response, "kepler, AL")

    @override_flag("organization_feature", active=True)
    @override_flag("organization_requests", active=True)
    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_requesting_entity_manage(self):
        """Tests the review steps page on under our manage context"""
        domain_request = completed_domain_request(
            user=self.user,
            # This is the additional details field
            has_anything_else=True,
        )
        domain_request.portfolio = self.portfolio
        domain_request.requested_suborganization = "moon"
        domain_request.suborganization_city = "kepler"
        domain_request.suborganization_state_territory = DomainRequest.StateTerritoryChoices.ALABAMA
        domain_request.save()
        domain_request.refresh_from_db()

        domain_request.submit()

        response = self.app.get(reverse("domain-request-status", kwargs={"pk": domain_request.pk}))
        self.assertContains(response, "Requesting entity")
        self.assertContains(response, "moon")
        self.assertContains(response, "kepler, AL")
