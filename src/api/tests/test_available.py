"""Test the available domain API."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory

from ..views import available

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
