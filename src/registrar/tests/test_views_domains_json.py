from registrar.models import UserDomainRole, Domain, DomainInformation, Portfolio
from django.urls import reverse

from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from .test_views import TestWithUser
from django_webtest import WebTest  # type: ignore
from django.utils.dateparse import parse_date
from api.tests.common import less_console_noise_decorator
from datetime import datetime, timedelta


class GetDomainsJsonTest(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        today = datetime.now()
        expiring_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        expiring_date_2 = (today + timedelta(days=31)).strftime("%Y-%m-%d")

        # Create test domains
        self.domain1 = Domain.objects.create(name="example1.com", expiration_date="2024-01-01", state="unknown")
        self.domain2 = Domain.objects.create(name="example2.com", expiration_date="2024-02-01", state="dns needed")
        self.domain3 = Domain.objects.create(name="example3.com", expiration_date="2024-03-01", state="ready")
        self.domain4 = Domain.objects.create(name="example4.com", expiration_date="2024-03-01", state="ready")
        self.domain5 = Domain.objects.create(name="example5.com", expiration_date=expiring_date, state="expiring soon")
        self.domain6 = Domain.objects.create(
            name="example6.com", expiration_date=expiring_date_2, state="expiring soon"
        )
        # Create UserDomainRoles
        UserDomainRole.objects.create(user=self.user, domain=self.domain1)
        UserDomainRole.objects.create(user=self.user, domain=self.domain2)
        UserDomainRole.objects.create(user=self.user, domain=self.domain3)

        UserDomainRole.objects.create(user=self.user, domain=self.domain5)
        UserDomainRole.objects.create(user=self.user, domain=self.domain6)

        # Create Portfolio
        self.portfolio = Portfolio.objects.create(requester=self.user, organization_name="Example org")

        # Add domain3 and domain4 to portfolio
        DomainInformation.objects.create(requester=self.user, domain=self.domain3, portfolio=self.portfolio)
        DomainInformation.objects.create(requester=self.user, domain=self.domain4, portfolio=self.portfolio)

    def tearDown(self):
        UserDomainRole.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
        Portfolio.objects.all().delete()
        super().tearDown()

    @less_console_noise_decorator
    def test_get_domains_json_unauthenticated(self):
        """for an unauthenticated user, test that the user is redirected for auth"""
        self.app.reset()

        response = self.client.get(reverse("get_domains_json"))
        self.assertEqual(response.status_code, 302)

    @less_console_noise_decorator
    def test_get_domains_json_authenticated(self):
        """Test that an authenticated user gets the list of 3 domains."""
        response = self.app.get(reverse("get_domains_json"))
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 5)

        # Expected domains
        expected_domains = [self.domain1, self.domain2, self.domain3]

        # Extract fields from response
        domain_ids = [domain["id"] for domain in data["domains"]]
        names = [domain["name"] for domain in data["domains"]]
        expiration_dates = [domain["expiration_date"] for domain in data["domains"]]
        states = [domain["state"] for domain in data["domains"]]
        state_displays = [domain["state_display"] for domain in data["domains"]]
        get_state_help_texts = [domain["get_state_help_text"] for domain in data["domains"]]
        action_urls = [domain["action_url"] for domain in data["domains"]]
        action_labels = [domain["action_label"] for domain in data["domains"]]
        svg_icons = [domain["svg_icon"] for domain in data["domains"]]

        # Check fields for each domain
        for i, expected_domain in enumerate(expected_domains):
            self.assertEqual(expected_domain.id, domain_ids[i])
            self.assertEqual(expected_domain.name, names[i])
            self.assertEqual(expected_domain.expiration_date, expiration_dates[i])
            self.assertEqual(expected_domain.state, states[i])

            # Parsing the expiration date from string to date
            parsed_expiration_date = parse_date(expiration_dates[i])
            expected_domain.expiration_date = parsed_expiration_date

            # Check state_display and get_state_help_text
            self.assertEqual(expected_domain.state_display(), state_displays[i])
            self.assertEqual(expected_domain.get_state_help_text(), get_state_help_texts[i])

            self.assertEqual(reverse("domain", kwargs={"domain_pk": expected_domain.id}), action_urls[i])

            # Check action_label
            action_label_expected = (
                "View"
                if expected_domains[i].state
                in [
                    Domain.State.DELETED,
                    Domain.State.ON_HOLD,
                ]
                else "Manage"
            )
            self.assertEqual(action_label_expected, action_labels[i])

            # Check svg_icon
            svg_icon_expected = (
                "visibility"
                if expected_domains[i].state
                in [
                    Domain.State.DELETED,
                    Domain.State.ON_HOLD,
                ]
                else "settings"
            )
            self.assertEqual(svg_icon_expected, svg_icons[i])

    @less_console_noise_decorator
    def test_get_domains_json_with_portfolio_view_managed_domains(self):
        """Test that an authenticated user gets the list of 1 domain for portfolio. The 1 domain
        is the domain that they manage within the portfolio."""

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS],
        )

        response = self.app.get(reverse("get_domains_json"), {"portfolio": self.portfolio.id})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 1)

        # Expected domains
        expected_domains = [self.domain3]

        # Extract fields from response
        domain_ids = [domain["id"] for domain in data["domains"]]
        names = [domain["name"] for domain in data["domains"]]
        expiration_dates = [domain["expiration_date"] for domain in data["domains"]]
        states = [domain["state"] for domain in data["domains"]]
        state_displays = [domain["state_display"] for domain in data["domains"]]
        get_state_help_texts = [domain["get_state_help_text"] for domain in data["domains"]]
        action_urls = [domain["action_url"] for domain in data["domains"]]
        action_labels = [domain["action_label"] for domain in data["domains"]]
        svg_icons = [domain["svg_icon"] for domain in data["domains"]]

        # Check fields for each domain
        for i, expected_domain in enumerate(expected_domains):
            self.assertEqual(expected_domain.id, domain_ids[i])
            self.assertEqual(expected_domain.name, names[i])
            self.assertEqual(expected_domain.expiration_date, expiration_dates[i])
            self.assertEqual(expected_domain.state, states[i])

            # Parsing the expiration date from string to date
            parsed_expiration_date = parse_date(expiration_dates[i])
            expected_domain.expiration_date = parsed_expiration_date

            # Check state_display and get_state_help_text
            self.assertEqual(expected_domain.state_display(), state_displays[i])
            self.assertEqual(expected_domain.get_state_help_text(), get_state_help_texts[i])

            self.assertEqual(reverse("domain", kwargs={"domain_pk": expected_domain.id}), action_urls[i])

            # Check action_label
            user_domain_role_exists = UserDomainRole.objects.filter(
                domain_id=expected_domains[i].id, user=self.user
            ).exists()
            action_label_expected = (
                "View"
                if not user_domain_role_exists
                or expected_domains[i].state
                in [
                    Domain.State.DELETED,
                    Domain.State.ON_HOLD,
                ]
                else "Manage"
            )
            self.assertEqual(action_label_expected, action_labels[i])

            # Check svg_icon
            svg_icon_expected = (
                "visibility"
                if not user_domain_role_exists
                or expected_domains[i].state
                in [
                    Domain.State.DELETED,
                    Domain.State.ON_HOLD,
                ]
                else "settings"
            )
            self.assertEqual(svg_icon_expected, svg_icons[i])

    @less_console_noise_decorator
    def test_get_domains_json_with_portfolio_view_all_domains(self):
        """Test that an authenticated user gets the list of 2 domains for portfolio. One is a domain which
        they manage within the portfolio. The other is a domain which they don't manage within the
        portfolio."""

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS],
        )

        response = self.app.get(reverse("get_domains_json"), {"portfolio": self.portfolio.id})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 2)

        # Expected domains
        expected_domains = [self.domain3, self.domain4]

        # Extract fields from response
        domain_ids = [domain["id"] for domain in data["domains"]]
        names = [domain["name"] for domain in data["domains"]]
        expiration_dates = [domain["expiration_date"] for domain in data["domains"]]
        states = [domain["state"] for domain in data["domains"]]
        state_displays = [domain["state_display"] for domain in data["domains"]]
        get_state_help_texts = [domain["get_state_help_text"] for domain in data["domains"]]
        action_urls = [domain["action_url"] for domain in data["domains"]]
        action_labels = [domain["action_label"] for domain in data["domains"]]
        svg_icons = [domain["svg_icon"] for domain in data["domains"]]

        # Check fields for each domain
        for i, expected_domain in enumerate(expected_domains):
            self.assertEqual(expected_domain.id, domain_ids[i])
            self.assertEqual(expected_domain.name, names[i])
            self.assertEqual(expected_domain.expiration_date, expiration_dates[i])
            self.assertEqual(expected_domain.state, states[i])

            # Parsing the expiration date from string to date
            parsed_expiration_date = parse_date(expiration_dates[i])
            expected_domain.expiration_date = parsed_expiration_date

            # Check state_display and get_state_help_text
            self.assertEqual(expected_domain.state_display(), state_displays[i])
            self.assertEqual(expected_domain.get_state_help_text(), get_state_help_texts[i])

            self.assertEqual(reverse("domain", kwargs={"domain_pk": expected_domain.id}), action_urls[i])

            # Check action_label
            user_domain_role_exists = UserDomainRole.objects.filter(
                domain_id=expected_domains[i].id, user=self.user
            ).exists()
            action_label_expected = (
                "View"
                if not user_domain_role_exists
                or expected_domains[i].state
                in [
                    Domain.State.DELETED,
                    Domain.State.ON_HOLD,
                ]
                else "Manage"
            )
            self.assertEqual(action_label_expected, action_labels[i])

            # Check svg_icon
            svg_icon_expected = (
                "visibility"
                if not user_domain_role_exists
                or expected_domains[i].state
                in [
                    Domain.State.DELETED,
                    Domain.State.ON_HOLD,
                ]
                else "settings"
            )
            self.assertEqual(svg_icon_expected, svg_icons[i])

    @less_console_noise_decorator
    def test_get_domains_json_search(self):
        """Test search."""
        # Define your URL variables as a dictionary
        url_vars = {"search_term": "e2"}

        # Use the params parameter to include URL variables
        response = self.app.get(reverse("get_domains_json"), params=url_vars)
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["unfiltered_total"], 5)

        # Check the number of domain requests
        self.assertEqual(len(data["domains"]), 1)

        # Extract fields from response
        domains = [request["name"] for request in data["domains"]]

        self.assertEqual(
            self.domain2.name,
            domains[0],
        )

    @less_console_noise_decorator
    def test_pagination(self):
        """Test that pagination is correct in the response"""
        response = self.app.get(reverse("get_domains_json"), {"page": 1})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)

    @less_console_noise_decorator
    def test_sorting(self):
        """test that sorting works properly in the response"""
        response = self.app.get(reverse("get_domains_json"), {"sort_by": "expiration_date", "order": "desc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by expiration_date in descending order
        expiration_dates = [domain["expiration_date"] for domain in data["domains"]]
        self.assertEqual(expiration_dates, sorted(expiration_dates, reverse=True))

        response = self.app.get(reverse("get_domains_json"), {"sort_by": "expiration_date", "order": "asc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by expiration_date in ascending order
        expiration_dates = [domain["expiration_date"] for domain in data["domains"]]
        self.assertEqual(expiration_dates, sorted(expiration_dates))

    @less_console_noise_decorator
    def test_sorting_by_state_display(self):
        """test that the state_display sorting works properly"""
        response = self.app.get(reverse("get_domains_json"), {"sort_by": "state_display", "order": "asc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by state_display in ascending order
        states = [domain["state_display"] for domain in data["domains"]]
        self.assertEqual(states, sorted(states))

        response = self.app.get(reverse("get_domains_json"), {"sort_by": "state_display", "order": "desc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by state_display in descending order
        states = [domain["state_display"] for domain in data["domains"]]
        self.assertEqual(states, sorted(states, reverse=True))

    @less_console_noise_decorator
    def test_state_filtering(self):
        """Test that different states in request get expected responses."""
        expected_values = [
            ("unknown", 1),
            ("ready", 0),
            ("expired", 2),
            ("ready,expired", 2),
            ("unknown,expired", 3),
            ("expiring", 2),
        ]

        for state, num_domains in expected_values:
            with self.subTest(state=state, num_domains=num_domains):
                response = self.app.get(reverse("get_domains_json"), {"status": state})
                self.assertEqual(response.status_code, 200)
                data = response.json
                self.assertEqual(len(data["domains"]), num_domains)
