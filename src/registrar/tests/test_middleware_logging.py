from django.test import TestCase
from django.urls import reverse
import io
import logging
import json
from registrar.config.settings import JsonFormatter
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
        self.logger = logging.getLogger("testlogger")
        self.handler.setFormatter(JsonFormatter())
        self.logger.addHandler(self.handler)
        self.logger.propagate = False

    def tearDown(self):
        clear_threadlocal()
        self.handler.close()

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
        log_data = json.loads(log_output)
        self.assertIn("test_middleware@gmail.com", log_data["message"])

    def test_no_user_info(self):
        self.client.get(reverse("domains"))

        self.logger.info("Anonymous Test")

        self.handler.flush()

        log_output = self.stream.getvalue()
        log_data = json.loads(log_output)
        self.assertNotIn("user", log_data["message"])
