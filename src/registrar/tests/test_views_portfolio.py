from unittest import skip
from unittest.mock import MagicMock, ANY, patch

from django.conf import settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from api.tests.common import less_console_noise_decorator
from registrar.models.portfolio import Portfolio

from .common import MockEppLib, MockSESClient, create_user  # type: ignore
from django_webtest import WebTest  # type: ignore
import boto3_mocking  # type: ignore

from registrar.utility.errors import (
    NameserverError,
    NameserverErrorCodes,
    SecurityEmailError,
    SecurityEmailErrorCodes,
    GenericError,
    GenericErrorCodes,
    DsDataError,
    DsDataErrorCodes,
)

from registrar.models import (
    DomainRequest,
    Domain,
    DomainInformation,
    DomainInvitation,
    Contact,
    PublicContact,
    Host,
    HostIP,
    UserDomainRole,
    User,
    FederalAgency,
)
from datetime import date, datetime, timedelta
from django.utils import timezone

from .common import less_console_noise
from .test_views import TestWithUser
from waffle.testutils import override_flag

import logging

logger = logging.getLogger(__name__)


class TestPortfolioViews(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.portfolio, _ = Portfolio.objects.get_or_create(creator=self.user, organization_name="Hotel California")
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    @less_console_noise_decorator
    def test_middleware_does_not_redirect_if_no_permission(self):
        """"""
        self.app.set_user(self.user.username)
        self.user.portfolio=self.portfolio
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
        """ """
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
        """"""
        self.app.set_user(self.user.username)
        self.user.portfolio=self.portfolio
        self.user.portfolio_additional_permissions = [User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO]
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertContains(portfolio_page, '<h1>Organization</h1>')

    @less_console_noise_decorator
    def test_middleware_redirects_to_portfolio_domains_page(self):
        """"""
        self.app.set_user(self.user.username)
        self.user.portfolio=self.portfolio
        self.user.portfolio_additional_permissions = [User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO, User.UserPortfolioPermissionChoices.VIEW_DOMAINS]
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, '<h1>Organization</h1>')
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')

    @less_console_noise_decorator
    def test_portfolio_domains_page_403_when_user_not_have_permission(self):
        """"""
        self.app.set_user(self.user.username)
        self.user.portfolio=self.portfolio
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(reverse("portfolio-domains", kwargs={"portfolio_id": self.portfolio.pk}), status=403)
            # Assert the response is a 403
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_portfolio_domain_requests_page_403_when_user_not_have_permission(self):
        """"""
        self.app.set_user(self.user.username)
        self.user.portfolio=self.portfolio
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(reverse("portfolio-domain-requests", kwargs={"portfolio_id": self.portfolio.pk}), status=403)
            # Assert the response is a 403
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator    
    def test_portfolio_organization_page_403_when_user_not_have_permission(self):
        """"""
        self.app.set_user(self.user.username)
        self.user.portfolio=self.portfolio
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            response = self.app.get(reverse("portfolio-organization", kwargs={"portfolio_id": self.portfolio.pk}), status=403)
            # Assert the response is a 403
            # Assert the response is a 403 Forbidden
            self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_navigation_links_hidden_when_user_not_have_permission(self):
        """This test is AMAZING"""
        self.app.set_user(self.user.username)
        self.user.portfolio=self.portfolio
        self.user.portfolio_additional_permissions = [User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO, User.UserPortfolioPermissionChoices.VIEW_DOMAINS, User.UserPortfolioPermissionChoices.VIEW_REQUESTS]
        self.user.save()
        self.user.refresh_from_db()
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertNotContains(portfolio_page, '<h1>Organization</h1>')
            self.assertContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertContains(portfolio_page, reverse("portfolio-domains", kwargs={"portfolio_id": self.portfolio.pk}))
            self.assertContains(portfolio_page, reverse("portfolio-domain-requests", kwargs={"portfolio_id": self.portfolio.pk}))

            self.user.portfolio_additional_permissions = [User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO]
            self.user.save()
            self.user.refresh_from_db()

            portfolio_page = self.app.get(reverse("home")).follow()

            self.assertContains(portfolio_page, self.portfolio.organization_name)
            self.assertContains(portfolio_page, '<h1>Organization</h1>')
            self.assertNotContains(portfolio_page, '<h1 id="domains-header">Domains</h1>')
            self.assertNotContains(portfolio_page, reverse("portfolio-domains", kwargs={"portfolio_id": self.portfolio.pk}))
            self.assertNotContains(portfolio_page, reverse("portfolio-domain-requests", kwargs={"portfolio_id": self.portfolio.pk}))

    def tearDown(self):
        Portfolio.objects.all().delete()
        UserDomainRole.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
        super().tearDown()
