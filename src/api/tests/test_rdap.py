"""Test the domain rdap lookup API."""

import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase

from ..views import available, check_domain_available
from .common import less_console_noise
from registrar.utility.errors import GenericError, GenericErrorCodes
from unittest.mock import call

from epplibwrapper import (
    commands,
)

API_BASE_PATH = "/api/v1/rdap/?domain="

class RdapAPITest(MockEppLib):
     """Test that the RDAP API can be called as expected."""

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
        self.client.force_login(self.user)
        response = self.client.get(API_BASE_PATH + "whitehouse.gov")
        self.assertContains(response, "RDAP")
        response_object = json.loads(response.content)
        self.assertIn("RDAP", response_object)