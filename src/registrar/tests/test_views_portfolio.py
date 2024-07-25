from django.urls import reverse
from api.tests.common import less_console_noise_decorator
from registrar.config import settings
from registrar.models.portfolio import Portfolio
from django_webtest import WebTest  # type: ignore
from registrar.models import (
    DomainRequest,
    Domain,
    DomainInformation,
    UserDomainRole,
    User,
)
from .test_views import TestWithUser
from waffle.testutils import override_flag

import logging

logger = logging.getLogger(__name__)


class TestPortfolio(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.portfolio, _ = Portfolio.objects.get_or_create(creator=self.user, organization_name="Hotel California")
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    @less_console_noise_decorator
    def test_middleware_does_not_redirect_if_no_permission(self):
        """Test that user with no portfolio permission is not redirected when attempting to access home"""
        self.app.set_user(self.user.username)
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
        self.user.portfolio_additional_permissions = [User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO]
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home"))
            # Assert that we're on the right page
            self.assertNotContains(portfolio_page, self.portfolio.organization_name)

    @less_console_noise_decorator
    def test_middleware_redirects_to_portfolio_organization_page(self):
        """Test that user with VIEW_PORTFOLIO is redirected to portfolio organization page"""
        self.app.set_user(self.user.username)
        self.user.portfolio = self.portfolio
        self.user.portfolio_additional_permissions = [User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO]
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertContains(portfolio_page, "<h1>Organization</h1>")

    @less_console_noise_decorator
    def test_middleware_redirects_to_portfolio_domains_page(self):
        """Test that user with VIEW_PORTFOLIO and VIEW_ALL_DOMAINS is redirected to portfolio domains page"""
        self.app.set_user(self.user.username)
        self.user.portfolio = self.portfolio
        self.user.portfolio_additional_permissions = [
            User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            User.UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
        ]
        self.user.save()
        self.user.refresh_from_db()
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
        self.user.portfolio = self.portfolio
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(
                reverse("portfolio-domains", kwargs={"portfolio_id": self.portfolio.pk}), status=403
            )
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_portfolio_domain_requests_page_403_when_user_not_have_permission(self):
        """Test that user without proper permission is denied access to portfolio domain view"""
        self.app.set_user(self.user.username)
        self.user.portfolio = self.portfolio
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(
                reverse("portfolio-domain-requests", kwargs={"portfolio_id": self.portfolio.pk}), status=403
            )
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_portfolio_organization_page_403_when_user_not_have_permission(self):
        """Test that user without proper permission is not allowed access to portfolio organization page"""
        self.app.set_user(self.user.username)
        self.user.portfolio = self.portfolio
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(
                reverse("portfolio-organization", kwargs={"portfolio_id": self.portfolio.pk}), status=403
            )
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_navigation_links_hidden_when_user_not_have_permission(self):
        """Test that navigation links are hidden when user does not have portfolio permissions"""
        self.app.set_user(self.user.username)
        self.user.portfolio = self.portfolio
        self.user.portfolio_additional_permissions = [
            User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
            User.UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
            User.UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
        ]
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, "<h1>Organization</h1>")
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertContains(
                portfolio_page, reverse("portfolio-domains", kwargs={"portfolio_id": self.portfolio.pk})
            )
            self.assertContains(
                portfolio_page, reverse("portfolio-domain-requests", kwargs={"portfolio_id": self.portfolio.pk})
            )

            # reducing portfolio permissions to just VIEW_PORTFOLIO, which should remove domains
            # and domain requests from nav
            self.user.portfolio_additional_permissions = [User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO]
            self.user.save()
            self.user.refresh_from_db()

            portfolio_page = self.app.get(reverse("home")).follow()

            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertContains(portfolio_page, "<h1>Organization</h1>")
            self.assertNotContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertNotContains(
                portfolio_page, reverse("portfolio-domains", kwargs={"portfolio_id": self.portfolio.pk})
            )
            self.assertNotContains(
                portfolio_page, reverse("portfolio-domain-requests", kwargs={"portfolio_id": self.portfolio.pk})
            )

    def tearDown(self):
        Portfolio.objects.all().delete()
        UserDomainRole.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
        super().tearDown()


class TestPortfolioOrganization(TestPortfolio):

    def test_portfolio_org_name(self):
        """Can load portfolio's org name page."""
        with override_flag("organization_feature", active=True):
            self.app.set_user(self.user.username)
            self.user.portfolio = self.portfolio
            self.user.portfolio_additional_permissions = [
                User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                User.UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            ]
            self.user.save()
            self.user.refresh_from_db()

            page = self.app.get(reverse("portfolio-organization", kwargs={"portfolio_id": self.portfolio.pk}))
            self.assertContains(
                page, "The name of your federal agency will be publicly listed as the domain registrant."
            )

    def test_domain_org_name_address_content(self):
        """Org name and address information appears on the page."""
        with override_flag("organization_feature", active=True):
            self.app.set_user(self.user.username)
            self.user.portfolio = self.portfolio
            self.user.portfolio_additional_permissions = [
                User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                User.UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            ]
            self.user.save()
            self.user.refresh_from_db()

            self.portfolio.organization_name = "Hotel California"
            self.portfolio.save()
            page = self.app.get(reverse("portfolio-organization", kwargs={"portfolio_id": self.portfolio.pk}))
            # Once in the sidenav, once in the main nav, once in the form
            self.assertContains(page, "Hotel California", count=3)

    def test_domain_org_name_address_form(self):
        """Submitting changes works on the org name address page."""
        with override_flag("organization_feature", active=True):
            self.app.set_user(self.user.username)
            self.user.portfolio = self.portfolio
            self.user.portfolio_additional_permissions = [
                User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                User.UserPortfolioPermissionChoices.EDIT_PORTFOLIO,
            ]
            self.user.save()
            self.user.refresh_from_db()

            self.portfolio.address_line1 = "1600 Penn Ave"
            self.portfolio.save()
            portfolio_org_name_page = self.app.get(
                reverse("portfolio-organization", kwargs={"portfolio_id": self.portfolio.pk})
            )
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

            portfolio_org_name_page.form["address_line1"] = "6 Downing st"
            portfolio_org_name_page.form["city"] = "London"

            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            success_result_page = portfolio_org_name_page.form.submit()
            self.assertEqual(success_result_page.status_code, 200)

            self.assertContains(success_result_page, "6 Downing st")
            self.assertContains(success_result_page, "London")
