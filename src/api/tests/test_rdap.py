"""Test the domain rdap lookup API."""

import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase

from ..views import rdap

API_BASE_PATH = "/api/v1/rdap/?domain="


class RdapViewTest(TestCase):
    """Test that the RDAP view function works as expected"""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create(username="username")
        self.factory = RequestFactory()

    def test_rdap_get_no_tld(self):
        """RDAP API successfully fetches RDAP for domain without a TLD"""
        request = self.factory.get(API_BASE_PATH + "whitehouse")
        request.user = self.user
        response = rdap(request, domain="whitehouse")
        # contains the right text
        self.assertContains(response, "rdap")
        # can be parsed into JSON with appropriate keys
        response_object = json.loads(response.content)
        self.assertIn("rdapConformance", response_object)

    def test_rdap_invalid_domain(self):
        """RDAP API accepts invalid domain queries and returns JSON response
        with appropriate error codes"""
        request = self.factory.get(API_BASE_PATH + "whitehouse.com")
        request.user = self.user
        response = rdap(request, domain="whitehouse.com")

        self.assertContains(response, "errorCode")
        response_object = json.loads(response.content)
        self.assertIn("errorCode", response_object)


class RdapAPITest(TestCase):
    """Test that the API can be called as expected."""

    def setUp(self):
        super().setUp()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        title = "title"
        phone = "8080102431"
        self.user = get_user_model().objects.create(
            username=username, title=title, first_name=first_name, last_name=last_name, email=email, phone=phone
        )

    def test_rdap_get(self):
        """Can call RDAP API"""
        self.client.force_login(self.user)
        response = self.client.get(API_BASE_PATH + "whitehouse.gov")
        self.assertContains(response, "rdap")
        response_object = json.loads(response.content)
        self.assertIn("rdapConformance", response_object)
