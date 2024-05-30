from registrar.models import UserDomainRole, Domain
from django.urls import reverse
from .test_views import TestWithUser
from django_webtest import WebTest  # type: ignore
from django.utils.dateparse import parse_date


class GetDomainsJsonTest(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)

        # Create test domains
        self.domain1 = Domain.objects.create(name="example1.com", expiration_date="2024-01-01", state="active")
        self.domain2 = Domain.objects.create(name="example2.com", expiration_date="2024-02-01", state="inactive")
        self.domain3 = Domain.objects.create(name="example3.com", expiration_date="2024-03-01", state="active")

        # Create UserDomainRoles
        UserDomainRole.objects.create(user=self.user, domain=self.domain1)
        UserDomainRole.objects.create(user=self.user, domain=self.domain2)
        UserDomainRole.objects.create(user=self.user, domain=self.domain3)

    def tearDown(self):
        super().tearDown()
        UserDomainRole.objects.all().delete()
        UserDomainRole.objects.all().delete()

    def test_get_domains_json_unauthenticated(self):
        """for an unauthenticated user, test that the user is redirected for auth"""
        self.app.reset()

        response = self.client.get(reverse("get_domains_json"))
        self.assertEqual(response.status_code, 302)
    
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
        self.assertEqual(len(data["domains"]), 3)

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
            
            self.assertEqual(f'/domain/{expected_domain.id}', action_urls[i])

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
