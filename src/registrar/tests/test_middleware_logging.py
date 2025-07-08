from django.test import TestCase
from django.urls import reverse
import io
import logging

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
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

    def tearDown(self):
        clear_threadlocal()
        self.handler.close()

    def test_no_user_info(self):
        self.client.get(reverse("domains"))

        self.logger.info("Anonymous Test")

        self.handler.flush()

        output = self.stream.getvalue()

        self.assertNotIn("user", output)
