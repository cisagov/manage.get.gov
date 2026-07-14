from django.test import TestCase, override_settings
from django.urls import reverse
import io
import json
import logging
import uuid
from registrar.config.settings import JsonFormatter
from django.contrib.auth import get_user_model
import registrar.registrar_middleware
from ..logging_context import clear_user_log_context


class RegisterLoggingMiddlewareTest(TestCase):
    """Test 'our' middleware logging."""

    def setUp(self):
        clear_user_log_context()
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.logger = logging.getLogger(registrar.registrar_middleware.__name__)
        self.handler.setFormatter(JsonFormatter())
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def tearDown(self):
        clear_user_log_context()
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

    def test_logging_disabled_in_non_production(self):
        self.client.get(reverse("health"))
        log_output = self.stream.getvalue()
        self.assertNotIn("Router log", log_output)

    def test_request_id_generated_when_header_missing(self):
        """A UUID4 is minted when the header is absent and echoed on the response."""
        response = self.client.get(reverse("health"))
        echoed = response["X-Request-ID"]
        # Must parse as a UUID4 (raises ValueError if not).
        parsed = uuid.UUID(echoed)
        self.assertEqual(parsed.version, 4)

    @override_settings(IS_PRODUCTION=True)
    def test_request_id_appears_in_log_json(self):
        """The JsonFormatter sends request_id as a top-level field on every log line."""
        self.client.get(reverse("health"), HTTP_X_REQUEST_ID="trace-id-xyz")
        self.handler.flush()
        log_lines = [line for line in self.stream.getvalue().splitlines() if line.strip()]
        matching = [json.loads(line) for line in log_lines if "trace-id-xyz" in line]
        self.assertTrue(matching, "No log line carried the request_id")
        for entry in matching:
            self.assertEqual(entry.get("request_id"), "trace-id-xyz")

    def test_db_middleware_reuses_request_id(self):
        """Both DB_CONN log lines carry the shared request_id as a structured JSON field."""
        response = self.client.get(reverse("health"), HTTP_X_REQUEST_ID="shared-id-42")
        self.handler.flush()
        self.assertEqual(response["X-Request-ID"], "shared-id-42")

        db_lines = [
            json.loads(line)
            for line in self.stream.getvalue().splitlines()
            if line.strip() and ("DB_CONN_START" in line or "DB_CONN_END" in line)
        ]
        self.assertEqual(len(db_lines), 2, "Expected one DB_CONN_START and one DB_CONN_END line")
        for entry in db_lines:
            self.assertEqual(entry.get("request_id"), "shared-id-42")
