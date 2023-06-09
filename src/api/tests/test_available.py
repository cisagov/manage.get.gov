"""Test the available domain API."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory

from ..views import available, _domains, in_domains
from .common import less_console_noise

API_BASE_PATH = "/api/v1/available/"


class AvailableViewTest(TestCase):

    """Test that the view function works as expected."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="username")
        self.factory = RequestFactory()

    def test_view_function(self):
        request = self.factory.get(API_BASE_PATH + "test.gov")
        request.user = self.user
        response = available(request, domain="test.gov")
        # has the right text in it
        self.assertContains(response, "available")
        # can be parsed as JSON
        response_object = json.loads(response.content)
        self.assertIn("available", response_object)

    def test_domain_list(self):
        """Test the domain list that is returned from Github.

        This does not mock out the external file, it is actually fetched from
        the internet.
        """
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

    def test_in_domains_dotgov(self):
        """Domain searches work without trailing .gov"""
        self.assertTrue(in_domains("gsa"))
        # input is lowercased so GSA.GOV should be found
        self.assertTrue(in_domains("GSA"))
        # This domain should not have been registered
        self.assertFalse(in_domains("igorville"))

    def test_not_available_domain(self):
        """gsa.gov is not available"""
        request = self.factory.get(API_BASE_PATH + "gsa.gov")
        request.user = self.user
        response = available(request, domain="gsa.gov")
        self.assertFalse(json.loads(response.content)["available"])

    def test_available_domain(self):
        """igorville.gov is still available"""
        request = self.factory.get(API_BASE_PATH + "igorville.gov")
        request.user = self.user
        response = available(request, domain="igorville.gov")
        self.assertTrue(json.loads(response.content)["available"])

    def test_available_domain_dotgov(self):
        """igorville.gov is still available even without the .gov suffix"""
        request = self.factory.get(API_BASE_PATH + "igorville")
        request.user = self.user
        response = available(request, domain="igorville")
        self.assertTrue(json.loads(response.content)["available"])

    def test_error_handling(self):
        """Calling with bad strings raises an error."""
        bad_string = "blah!;"
        request = self.factory.get(API_BASE_PATH + bad_string)
        request.user = self.user
        response = available(request, domain=bad_string)
        self.assertFalse(json.loads(response.content)["available"])


class AvailableAPITest(TestCase):

    """Test that the API can be called as expected."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="username")

    def test_available_get(self):
        self.client.force_login(self.user)
        response = self.client.get(API_BASE_PATH + "nonsense")
        self.assertContains(response, "available")
        response_object = json.loads(response.content)
        self.assertIn("available", response_object)

    def test_available_post(self):
        """Cannot post to the /available/ API endpoint."""
        # have to log in to test the correct thing now that we require login
        # for all URLs by default
        self.client.force_login(self.user)
        with less_console_noise():
            response = self.client.post(API_BASE_PATH + "nonsense")
        self.assertEqual(response.status_code, 405)
