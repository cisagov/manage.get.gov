from django.test import TestCase
from registrar.config.settings import UserFormatter
from django.urls import reverse

import io
import logging

from django.contrib.auth import get_user_model


class UserInfoLoggingMiddlewareTest(TestCase):
    """Test 'our' middleware logging."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="test",
            first_name="test",
            email="test_middleware@gmail.com",
            phone="8002224444",
        )
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(UserFormatter("%(message)s"))
        self.logger = logging.getLogger("testlogger")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

    def tearDown(self):
        self.logger.removeHandler(self.handler)

    def test_middleware_sets_user_email(self):
        self.client.force_login(self.user)
        self.client.get(reverse("domains"))

        # adding log info to test

        self.logger.info("Testing middleware")
        self.handler.flush()
        log_output = self.stream.getvalue()
        self.assertIn(self.user.email, log_output)
        self.assertIn("Testing middleware", log_output)

    def test_no_user_info(self):
        self.client.get(reverse("domains"))

        self.logger.info("Anonymous Test")

        self.handler.flush()

        output = self.stream.getvalue()

        self.assertNotIn("email", output)
