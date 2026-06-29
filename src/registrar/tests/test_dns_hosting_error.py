import pickle  # nosec B403  # test-only: round-trips our own exception, never untrusted data

from django.test import TestCase

from registrar.utility.errors import (
    DnsHostingError,
    DnsHostingErrorCodes as codes,
    DnsNotFoundError,
    DnsValidationError,
    DnsRateLimitError,
    DnsAuthError,
    DnsTransportError,
    DnsUpstreamError,
    _DNS_WIRE_CODES,
)
from registrar.validations import DNS_RECORD_NAME_CONFLICT_ERROR_MESSAGE

# (subclass, default code, sample upstream_status) for each row of the
# wire-code reference. The base class is included with its UNKNOWN default.
DNS_ERROR_ROWS = [
    (DnsHostingError, codes.UNKNOWN, None),
    (DnsNotFoundError, codes.NOT_FOUND, 404),
    (DnsValidationError, codes.VALIDATION_FAILED, 400),
    (DnsRateLimitError, codes.RATE_LIMIT_EXCEEDED, 429),
    (DnsAuthError, codes.AUTH_FAILED, 401),
    (DnsTransportError, codes.UPSTREAM_TIMEOUT, None),
    (DnsUpstreamError, codes.UPSTREAM_ERROR, 500),
]


class TestDnsHostingError(TestCase):
    def test_subclasses_default_to_their_code(self):
        """Each subclass defaults `code` to its row in the wire-code reference."""
        for exc_cls, default_code, _ in DNS_ERROR_ROWS:
            with self.subTest(exc_cls=exc_cls.__name__):
                exc = exc_cls()
                self.assertEqual(exc.code, default_code)

    def test_message_resolves_from_error_mapping(self):
        """A user-facing message is resolved from `_error_mapping` for every code."""
        for code in codes:
            with self.subTest(code=code.name):
                exc = DnsHostingError(code=code)
                self.assertEqual(exc.message, DnsHostingError._error_mapping[code])
                self.assertEqual(str(exc), exc.message)

    def test_all_dns_hosting_error_codes_are_wired(self):
        self.assertLessEqual(set(codes), set(_DNS_WIRE_CODES))

    def test_record_conflict_reuses_model_validation_string(self):
        """RECORD_CONFLICT reuses the existing model-level validation copy, not a new string."""
        self.assertEqual(
            DnsValidationError(code=codes.RECORD_CONFLICT).message,
            DNS_RECORD_NAME_CONFLICT_ERROR_MESSAGE,
        )

    def test_explicit_message_wins_over_mapping(self):
        """A caller-supplied message overrides the code-level default."""
        exc = DnsValidationError(message="custom copy")
        self.assertEqual(exc.message, "custom copy")

    def test_wire_code_is_stable_name(self):
        """`wire_code` returns the stable wire name for the error's code."""
        self.assertEqual(DnsNotFoundError().wire_code, "DNS_NOT_FOUND")
        self.assertEqual(DnsHostingError(code=codes.UNKNOWN).wire_code, "DNS_UNKNOWN")

    def test_context_is_copied_to_plain_dict(self):
        """`context` is copied so the exception never holds a caller's object."""
        original = {"zone_id": "abc123"}
        exc = DnsNotFoundError(context=original)
        self.assertEqual(exc.context, original)
        self.assertIsNot(exc.context, original)
        # No context defaults to an empty dict, not None.
        self.assertEqual(DnsNotFoundError().context, {})

    def test_every_subclass_survives_pickling(self):
        """Pickle/unpickle every subclass and confirm the fields round-trip.

        The parallel test runner serializes exceptions across processes, so each
        subclass must store only simple values (str, int, dict of primitives).
        """
        for exc_cls, default_code, upstream_status in DNS_ERROR_ROWS:
            with self.subTest(exc_cls=exc_cls.__name__):
                context = {"zone_id": "abc123", "attempt": 2}
                exc = exc_cls(upstream_status=upstream_status, context=context)

                restored = pickle.loads(pickle.dumps(exc))  # nosec B301  # round-trips our own exception

                self.assertIs(type(restored), exc_cls)
                self.assertEqual(restored.code, default_code)
                self.assertEqual(restored.code, exc.code)
                self.assertEqual(restored.upstream_status, upstream_status)
                self.assertEqual(restored.context, context)
                self.assertEqual(restored.message, exc.message)
                self.assertEqual(restored.wire_code, exc.wire_code)

    def test_explicit_message_survives_pickling(self):
        """A caller-supplied message round-trips through pickle unchanged."""
        exc = DnsUpstreamError(message="provider on fire", upstream_status=503)
        restored = pickle.loads(pickle.dumps(exc))  # nosec B301  # round-trips our own exception
        self.assertEqual(restored.message, "provider on fire")
        self.assertEqual(restored.upstream_status, 503)
