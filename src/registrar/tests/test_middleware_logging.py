from django.test import TestCase, RequestFactory, override_settings
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User

from registrar.registrar_middleware import RequestLoggingMiddleware


class RequestLoggingMiddlewareTest(TestCase):
    """Test 'our' middleware logging."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response_mock = MagicMock()
        self.middleware = RequestLoggingMiddleware(self.get_response_mock)

    @override_settings(IS_PRODUCTION=True)  # Scopes change to this test only
    @patch("logging.Logger.info")
    def test_logging_enabled_in_production(self, mock_logger):
        """Test that logging occurs when IS_PRODUCTION is True"""
        request = self.factory.get("/test-path", **{"REMOTE_ADDR": "Unknown IP"})  # Override IP
        request.user = User(username="testuser", email="testuser@example.com")

        self.middleware(request)  # Call middleware

        mock_logger.assert_called_once_with(
            "Router log | User: testuser@example.com | IP: Unknown IP | Path: /test-path"
        )

    @patch("logging.Logger.info")
    def test_logging_disabled_in_non_production(self, mock_logger):
        """Test that logging does not occur when IS_PRODUCTION is False"""
        request = self.factory.get("/test-path")
        request.user = User(username="testuser", email="testuser@example.com")

        self.middleware(request)  # Call middleware

        mock_logger.assert_not_called()  # Ensure no logs are generated

    @override_settings(IS_PRODUCTION=True)  # Scopes change to this test only
    @patch("logging.Logger.info")
    def test_logging_anonymous_user(self, mock_logger):
        """Test logging for an anonymous user"""
        request = self.factory.get("/anonymous-path", **{"REMOTE_ADDR": "Unknown IP"})  # Override IP
        request.user = AnonymousUser()  # Simulate an anonymous user

        self.middleware(request)  # Call middleware

        mock_logger.assert_called_once_with("Router log | User: Anonymous | IP: Unknown IP | Path: /anonymous-path")
