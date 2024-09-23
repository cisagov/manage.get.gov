from django.urls import reverse
from django.test import TestCase, Client
from registrar.models import FederalAgency, SeniorOfficial, User, DomainRequest
from django.contrib.auth import get_user_model
from registrar.tests.common import create_superuser, create_user, completed_domain_request

from api.tests.common import less_console_noise_decorator
from registrar.utility.constants import BranchChoices


class GetSeniorOfficialJsonTest(TestCase):
    def setUp(self):
        self.client = Client()
        p = "password"
        self.user = get_user_model().objects.create_user(username="testuser", password=p)

        self.superuser = create_superuser()
        self.analyst_user = create_user()

        self.agency = FederalAgency.objects.create(agency="Test Agency")
        self.senior_official = SeniorOfficial.objects.create(
            first_name="John", last_name="Doe", title="Director", federal_agency=self.agency
        )

        self.api_url = reverse("get-senior-official-from-federal-agency-json")

    def tearDown(self):
        User.objects.all().delete()
        SeniorOfficial.objects.all().delete()
        FederalAgency.objects.all().delete()

    @less_console_noise_decorator
    def test_get_senior_official_json_authenticated_superuser(self):
        """Test that a superuser can fetch the senior official information."""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(self.api_url, {"agency_name": "Test Agency"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.senior_official.id)
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")
        self.assertEqual(data["title"], "Director")

    @less_console_noise_decorator
    def test_get_senior_official_json_authenticated_analyst(self):
        """Test that an analyst user can fetch the senior official's information."""
        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(self.api_url, {"agency_name": "Test Agency"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.senior_official.id)
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")
        self.assertEqual(data["title"], "Director")

    @less_console_noise_decorator
    def test_get_senior_official_json_unauthenticated(self):
        """Test that an unauthenticated user receives a 403 with an error message."""
        p = "password"
        self.client.login(username="testuser", password=p)
        response = self.client.get(self.api_url, {"agency_name": "Test Agency"})
        self.assertEqual(response.status_code, 302)

    @less_console_noise_decorator
    def test_get_senior_official_json_not_found(self):
        """Test that a request for a non-existent agency returns a 404 with an error message."""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(self.api_url, {"agency_name": "Non-Federal Agency"})
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"], "Senior Official not found")


class GetFederalPortfolioTypeJsonTest(TestCase):
    def setUp(self):
        self.client = Client()
        p = "password"
        self.user = get_user_model().objects.create_user(username="testuser", password=p)

        self.superuser = create_superuser()
        self.analyst_user = create_user()

        self.agency = FederalAgency.objects.create(agency="Test Agency", federal_type=BranchChoices.JUDICIAL)

        self.api_url = reverse("get-federal-and-portfolio-types-from-federal-agency-json")

    def tearDown(self):
        User.objects.all().delete()
        FederalAgency.objects.all().delete()

    @less_console_noise_decorator
    def test_get_federal_and_portfolio_types_json_authenticated_superuser(self):
        """Test that a superuser can fetch the federal and portfolio types."""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(self.api_url, {"agency_name": "Test Agency", "organization_type": "federal"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["federal_type"], "Judicial")
        self.assertEqual(data["portfolio_type"], "Federal - Judicial")

    @less_console_noise_decorator
    def test_get_federal_and_portfolio_types_json_authenticated_regularuser(self):
        """Test that a regular user receives a 403 with an error message."""
        p = "password"
        self.client.login(username="testuser", password=p)
        response = self.client.get(self.api_url, {"agency_name": "Test Agency", "organization_type": "federal"})
        self.assertEqual(response.status_code, 302)


class GetActionNeededEmailForUserJsonTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = create_superuser()
        self.analyst_user = create_user()
        self.agency = FederalAgency.objects.create(agency="Test Agency")
        self.domain_request = completed_domain_request(
            federal_agency=self.agency,
            name="test.gov",
            status=DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        )

        self.api_url = reverse("get-action-needed-email-for-user-json")

    def tearDown(self):
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        FederalAgency.objects.all().delete()

    @less_console_noise_decorator
    def test_get_action_needed_email_for_user_json_superuser(self):
        """Test that a superuser can fetch the action needed email."""
        self.client.force_login(self.superuser)

        response = self.client.get(
            self.api_url,
            {
                "reason": DomainRequest.ActionNeededReasons.ELIGIBILITY_UNCLEAR,
                "domain_request_id": self.domain_request.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("action_needed_email", data)
        self.assertIn("ORGANIZATION MAY NOT MEET ELIGIBILITY REQUIREMENTS", data["action_needed_email"])

    @less_console_noise_decorator
    def test_get_action_needed_email_for_user_json_analyst(self):
        """Test that an analyst can fetch the action needed email."""
        self.client.force_login(self.analyst_user)

        response = self.client.get(
            self.api_url,
            {
                "reason": DomainRequest.ActionNeededReasons.QUESTIONABLE_SENIOR_OFFICIAL,
                "domain_request_id": self.domain_request.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("action_needed_email", data)
        self.assertIn("SENIOR OFFICIAL DOES NOT MEET ELIGIBILITY REQUIREMENTS", data["action_needed_email"])

    @less_console_noise_decorator
    def test_get_action_needed_email_for_user_json_regular(self):
        """Test that a regular user receives a 403 with an error message."""
        p = "password"
        self.client.login(username="testuser", password=p)
        response = self.client.get(
            self.api_url,
            {
                "reason": DomainRequest.ActionNeededReasons.QUESTIONABLE_SENIOR_OFFICIAL,
                "domain_request_id": self.domain_request.id,
            },
        )
        self.assertEqual(response.status_code, 302)
