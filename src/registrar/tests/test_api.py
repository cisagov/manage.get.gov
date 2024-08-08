from django.urls import reverse
from django.test import TestCase, Client
from registrar.models import FederalAgency, SeniorOfficial, User
from django.contrib.auth import get_user_model
from registrar.tests.common import create_superuser, create_user


class GetSeniorOfficialJsonTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="testuser", password="password")

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

    def test_get_senior_official_json_authenticated_superuser(self):
        """Test that a superuser can fetch the senior official information."""
        self.client.login(username="superuser", password="adminpass")
        response = self.client.get(self.api_url, {"agency_name": "Test Agency"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.senior_official.id)
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")
        self.assertEqual(data["title"], "Director")

    def test_get_senior_official_json_authenticated_analyst(self):
        """Test that an analyst user can fetch the senior official's information."""
        self.client.login(username="staffuser", password="userpass")
        response = self.client.get(self.api_url, {"agency_name": "Test Agency"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.senior_official.id)
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")
        self.assertEqual(data["title"], "Director")

    def test_get_senior_official_json_unauthenticated(self):
        """Test that an unauthenticated user receives a 403 with an error message."""
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.api_url, {"agency_name": "Test Agency"})
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "You do not have access to this resource")

    def test_get_senior_official_json_not_found(self):
        """Test that a request for a non-existent agency returns a 404 with an error message."""
        self.client.login(username="superuser", password="adminpass")
        response = self.client.get(self.api_url, {"agency_name": "Non-Federal Agency"})
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"], "Senior Official not found")
