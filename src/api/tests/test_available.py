"""Test the available domain API."""

import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings

from ..views import available, check_domain_available
from .common import less_console_noise
from registrar.tests.common import MockEppLib
from registrar.utility.errors import GenericError, GenericErrorCodes
from unittest.mock import call

from epplibwrapper import (
    commands,
)

API_BASE_PATH = "/api/v1/available/?domain="


@override_settings(IS_LOCAL=False)
class AvailableViewTest(MockEppLib):
    """Test that the view function works as expected."""

    def setUp(self):
        super().setUp()
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

    def test_domain_available_makes_calls_(self):
        """Domain searches successfully make correct mock EPP calls"""
        gsa_available = check_domain_available("gsa.gov")
        igorville_available = check_domain_available("igorville.gov")

        """Domain searches successfully make mock EPP calls"""
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.CheckDomain(
                        ["gsa.gov"],
                    ),
                    cleaned=True,
                ),
                call(
                    commands.CheckDomain(
                        ["igorville.gov"],
                    ),
                    cleaned=True,
                ),
            ]
        )
        """Domain searches return correct availability results"""
        self.assertFalse(gsa_available)
        self.assertTrue(igorville_available)

    def test_domain_available_capitalized(self):
        """Domain searches work without case sensitivity"""
        self.assertFalse(check_domain_available("gsa.gov"))
        self.assertTrue(check_domain_available("igorville.gov"))
        # input is lowercased so GSA.GOV should also not be available
        self.assertFalse(check_domain_available("GSA.gov"))
        # input is lowercased so IGORVILLE.GOV should also be available
        self.assertTrue(check_domain_available("IGORVILLE.gov"))

    def test_domain_available_dotgov(self):
        """Domain searches work without trailing .gov"""
        self.assertFalse(check_domain_available("gsa"))
        # input is lowercased so GSA.GOV should be found
        self.assertFalse(check_domain_available("GSA"))
        # This domain should be available to register
        self.assertTrue(check_domain_available("igorville"))

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

    def test_bad_string_handling(self):
        """Calling with bad strings returns unavailable."""
        bad_string = "blah!;"
        request = self.factory.get(API_BASE_PATH + bad_string)
        request.user = self.user
        response = available(request, domain=bad_string)
        self.assertFalse(json.loads(response.content)["available"])

    def test_error_handling(self):
        """Error thrown while calling availabilityAPI returns error."""
        request = self.factory.get(API_BASE_PATH + "errordomain.gov")
        request.user = self.user
        # domain set to raise error returns false for availability and error message
        error_domain_response = available(request, domain="errordomain.gov")
        self.assertFalse(json.loads(error_domain_response.content)["available"])
        self.assertEqual(
            GenericError.get_error_message(GenericErrorCodes.CANNOT_CONTACT_REGISTRY),
            json.loads(error_domain_response.content)["message"],
        )


class AvailableAPITest(MockEppLib):
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
