from django.test import TestCase
from registrar.config.settings import UserFormatter
from django.urls import reverse

import io
import logging

from django.contrib.auth import get_user_model
from ..thread_locals import _user_local


def clear_threadlocal():
    for attr in ["ip", "user_email", "request_path"]:
        if hasattr(_user_local, attr):
            delattr(_user_local, attr)


class RegisterLoggingMiddlewareTest(TestCase):
    """Test 'our' middleware logging."""

    def setUp(self):
        clear_threadlocal()
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(UserFormatter("%(message)s"))
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

    def tearDown(self):
        self.logger.removeHandler(self.handler)
        clear_threadlocal()
        self.handler.close()

    def test_no_user_info(self):
        self.client.get(reverse("domains"))

        self.logger.info("Anonymous Test")

        self.handler.flush()

        output = self.stream.getvalue()

        self.assertNotIn("user", output)

    def test_middleware_sets_user_email(self):
        user = get_user_model().objects.create_user(
            username="test",
            first_name="test",
            email="test_middleware@gmail.com",
            phone="8002224444",
        )
        self.client.force_login(user)
        self.client.get(reverse("domains"))

        # adding log info to test

        self.logger.info("Testing middleware")
        self.handler.flush()
        log_output = self.stream.getvalue()
        self.client.logout()
        self.assertIn(user.email, log_output)
        self.assertIn("Testing middleware", log_output)
