"""Test the available domain API."""

import json

from django.test import client, TestCase, RequestFactory

from ..views import available

class AvailableViewTest(TestCase):

    """Test that the view function works as expected."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_view_function(self):
        request = self.factory.get("available/test.gov")
        response = available(request, domain="test.gov")
        # has the right text in it
        self.assertContains(response, "available")
        # can be parsed as JSON
        response_object = json.loads(response.content)
        self.assertIn("available", response_object)


class AvailableAPITest(TestCase):

    """Test that the API can be called as expected."""

    def test_available_get(self):
        response = self.client.get("/available/nonsense")
        self.assertContains(response, "available")
        response_object = json.loads(response.content)
        self.assertIn("available", response_object)

    def test_available_post(self):
        """Cannot post to the /available/ API endpoint."""
        response = self.client.post("/available/nonsense")
        self.assertEqual(response.status_code, 405)
