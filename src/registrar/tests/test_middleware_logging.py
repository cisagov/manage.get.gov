from django.test import TestCase, override_settings
from django.urls import reverse
import io
import logging
from registrar.config.settings import JsonFormatter
from django.contrib.auth import get_user_model
import registrar.registrar_middleware

class RegisterLoggingMiddlewareTest(TestCase):
    """Test 'our' middleware logging."""

    def setUp(self):
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.logger = logging.getLogger(registrar.registrar_middleware.__name__)
        self.handler.setFormatter(JsonFormatter())
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def tearDown(self):
        self.handler.close()

    @override_settings(IS_PRODUCTION=True)  # Scopes change to this test only
    def test_logging_with_anonymous_user(self):
        self.client.get(reverse("health"))
        log_output = self.stream.getvalue()
        self.assertIn("Router log", log_output)
        self.assertIn("user: Anonymous", log_output)

    @override_settings(IS_PRODUCTION=True)
    def test_logging_with_nonanonymous_user(self):
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
        self.client.session.flush()
        self.assertIn("test_middleware@gmail.com", log_output)