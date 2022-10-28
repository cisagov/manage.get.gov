"""Test the available domain API."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory

from ..views import available, _domains, in_domains


class AvailableViewTest(TestCase):

    """Test that the view function works as expected."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="username")
        self.factory = RequestFactory()

    def test_view_function(self):
        request = self.factory.get("/available/test.gov")
        request.user = self.user
        response = available(request, domain="test.gov")
        # has the right text in it
        self.assertContains(response, "available")
        # can be parsed as JSON
        response_object = json.loads(response.content)
        self.assertIn("available", response_object)

    def test_domain_list(self):
        """Test the domain list that is returned."""
        domains = _domains()
        self.assertIn("gsa.gov", domains)
        # entries are all lowercase so GSA.GOV is not in the set
        self.assertNotIn("GSA.GOV", domains)
        self.assertNotIn("igorville.gov", domains)
        # all the entries have dots
        self.assertNotIn("gsa", domains)

    def test_in_domains(self):
        self.assertTrue(in_domains("gsa.gov"))
        # input is lowercased so GSA.GOV should be found
        self.assertTrue(in_domains("GSA.GOV"))
        # This domain should not have been registered
        self.assertFalse(in_domains("igorville.gov"))
        # all the entries have dots
        self.assertFalse(in_domains("gsa"))

    def test_not_available_domain(self):
        """gsa.gov is not available"""
        request = self.factory.get("/available/gsa.gov")
        request.user = self.user
        response = available(request, domain="gsa.gov")
        self.assertFalse(json.loads(response.content)["available"])

    def test_available_domain(self):
        """igorville.gov is still available"""
        request = self.factory.get("/available/igorville.gov")
        request.user = self.user
        response = available(request, domain="igorville.gov")
        self.assertTrue(json.loads(response.content)["available"])


class AvailableAPITest(TestCase):

    """Test that the API can be called as expected."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="username")

    def test_available_get(self):
        self.client.force_login(self.user)
        response = self.client.get("/available/nonsense")
        self.assertContains(response, "available")
        response_object = json.loads(response.content)
        self.assertIn("available", response_object)

    def test_available_post(self):
        """Cannot post to the /available/ API endpoint."""
        response = self.client.post("/available/nonsense")
        self.assertEqual(response.status_code, 405)
