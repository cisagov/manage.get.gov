"""Unit tests for the DnsHostingError hierarchy and the dns_error_response envelope.

Prototype scope — covers only the pieces wired end-to-end for the
"create DNS record → zone not found" path. Full per-subclass coverage lands
with sub-ticket #1.

See docs/developer/dns-error-handling.md.
"""

import json
import pickle  # nosec B403 — used only in tests to assert exception pickle-safety
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase
from httpx import HTTPStatusError, RequestError

from registrar.utility.api_responses import dns_error_response
from registrar.utility.errors import (
    APIError,
    DnsHostingError,
    DnsHostingErrorCodes,
    DnsNotFoundError,
    classify_legacy_dns_exception,
)


class TestDnsHostingError(SimpleTestCase):
    def test_code_maps_to_default_message(self):
        exc = DnsHostingError(code=DnsHostingErrorCodes.ZONE_NOT_FOUND)
        self.assertIn("DNS zone", exc.message)
        self.assertEqual(exc.code, DnsHostingErrorCodes.ZONE_NOT_FOUND)

    def test_wire_code_for_zone_not_found(self):
        exc = DnsNotFoundError()
        self.assertEqual(exc.wire_code, "DNS_ZONE_NOT_FOUND")

    def test_context_is_copied_not_referenced(self):
        ctx = {"zone_id": "abc"}
        exc = DnsNotFoundError(context=ctx)
        ctx["zone_id"] = "mutated"
        self.assertEqual(exc.context["zone_id"], "abc")

    def test_pickle_round_trip_preserves_state(self):
        exc = DnsNotFoundError(
            upstream_status=404,
            context={"zone_id": "abc123", "cf_ray": "xyz"},
        )
        restored = pickle.loads(pickle.dumps(exc))  # nosec B301 — test-only round-trip
        self.assertIsInstance(restored, DnsNotFoundError)
        self.assertEqual(restored.code, exc.code)
        self.assertEqual(restored.message, exc.message)
        self.assertEqual(restored.upstream_status, exc.upstream_status)
        self.assertEqual(restored.context, exc.context)


class TestDnsErrorResponseEnvelope(SimpleTestCase):
    def test_envelope_shape(self):
        # RequestLoggingMiddleware stashes _dns_request_id on the request;
        # SimpleNamespace is a lightweight stand-in for a Django HttpRequest.
        request = SimpleNamespace(_dns_request_id="req-123")
        exc = DnsNotFoundError(upstream_status=404, context={"zone_id": "abc"})

        response = dns_error_response(exc, request=request)
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.content)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["code"], "DNS_ZONE_NOT_FOUND")
        self.assertIn("DNS zone", body["message"])
        self.assertEqual(body["request_id"], "req-123")

    def test_envelope_request_id_null_when_request_missing(self):
        exc = DnsNotFoundError()
        response = dns_error_response(exc)
        body = json.loads(response.content)
        self.assertIsNone(body["request_id"])


class TestClassifyLegacyDnsException(SimpleTestCase):
    """Bridge helper — populates error_code on DnsOperationLog rows until
    a follow-up ticket migrates CloudflareService to raise typed errors everywhere."""

    def _http_status_error(self, status):
        response = Mock()
        response.status_code = status
        err = HTTPStatusError(message="boom", request=Mock(), response=response)
        err.response = response
        return err

    def test_typed_dns_hosting_error_passes_through(self):
        exc = DnsNotFoundError(upstream_status=404)
        self.assertEqual(classify_legacy_dns_exception(exc), ("DNS_ZONE_NOT_FOUND", 404))

    def test_http_status_404(self):
        self.assertEqual(classify_legacy_dns_exception(self._http_status_error(404)), ("DNS_ZONE_NOT_FOUND", 404))

    def test_http_status_403_maps_to_auth_failed(self):
        self.assertEqual(classify_legacy_dns_exception(self._http_status_error(403)), ("DNS_AUTH_FAILED", 403))

    def test_http_status_429_maps_to_rate_limit(self):
        self.assertEqual(
            classify_legacy_dns_exception(self._http_status_error(429)),
            ("DNS_RATE_LIMIT_EXCEEDED", 429),
        )

    def test_http_status_5xx_maps_to_upstream_error(self):
        self.assertEqual(classify_legacy_dns_exception(self._http_status_error(502)), ("DNS_UPSTREAM_ERROR", 502))

    def test_request_error_maps_to_upstream_timeout(self):
        self.assertEqual(classify_legacy_dns_exception(RequestError("timeout")), ("DNS_UPSTREAM_TIMEOUT", None))

    def test_api_error_parses_status_from_message(self):
        exc = APIError("Cloudflare create_dns_record failed: 400 bad request body")
        self.assertEqual(classify_legacy_dns_exception(exc), ("DNS_VALIDATION_FAILED", 400))

    def test_unknown_exception_falls_back(self):
        self.assertEqual(classify_legacy_dns_exception(RuntimeError("wat")), ("DNS_UNKNOWN", None))
