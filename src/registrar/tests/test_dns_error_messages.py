"""Tests for the view-layer DNS error -> form field message resolver (ticket #4672)."""

from django.test import SimpleTestCase

from registrar.utility.dns_error_messages import (
    DNS_A_AAAA_CONFLICT_ON_CNAME_ERROR_MESSAGE,
    DNS_CNAME_CONFLICT_ON_A_AAAA_ERROR_MESSAGE,
    DNS_DUPLICATE_RECORD_ERROR_MESSAGE,
    DNS_GENERIC_VALIDATION_ERROR_MESSAGE,
    DNS_TXT_LENGTH_LIMIT_ERROR_MESSAGE,
    resolve_dns_error_messages,
)
from registrar.utility.errors import (
    DnsContentLengthExceededError,
    DnsDuplicateRecordError,
    DnsNameConflictError,
    DnsValidationError,
)


class TestResolveDnsErrorMessages(SimpleTestCase):
    def test_duplicate_record_error_maps_to_nonfield_duplicate_message(self):
        result = resolve_dns_error_messages(DnsDuplicateRecordError(submitted_record_type="A"))
        self.assertEqual(result, {"__all__": [DNS_DUPLICATE_RECORD_ERROR_MESSAGE]})

    def test_name_conflict_on_a_submission_shows_cname_exists_copy(self):
        result = resolve_dns_error_messages(DnsNameConflictError(submitted_record_type="A"))
        self.assertEqual(result, {"name": [DNS_CNAME_CONFLICT_ON_A_AAAA_ERROR_MESSAGE]})

    def test_name_conflict_on_aaaa_submission_shows_cname_exists_copy(self):
        result = resolve_dns_error_messages(DnsNameConflictError(submitted_record_type="AAAA"))
        self.assertEqual(result, {"name": [DNS_CNAME_CONFLICT_ON_A_AAAA_ERROR_MESSAGE]})

    def test_name_conflict_on_cname_submission_shows_a_aaaa_exists_copy(self):
        result = resolve_dns_error_messages(DnsNameConflictError(submitted_record_type="CNAME"))
        self.assertEqual(result, {"name": [DNS_A_AAAA_CONFLICT_ON_CNAME_ERROR_MESSAGE]})

    def test_content_length_exceeded_error_maps_to_content_field_message(self):
        result = resolve_dns_error_messages(DnsContentLengthExceededError(submitted_record_type="TXT"))
        self.assertEqual(result, {"content": [DNS_TXT_LENGTH_LIMIT_ERROR_MESSAGE]})

    def test_unknown_validation_error_with_vendor_message_is_surfaced_as_nonfield(self):
        result = resolve_dns_error_messages(DnsValidationError("Something specific from vendor."))
        self.assertEqual(result, {"__all__": ["Something specific from vendor."]})

    def test_unknown_validation_error_without_message_falls_back_to_generic_copy(self):
        result = resolve_dns_error_messages(DnsValidationError())
        self.assertEqual(result, {"__all__": [DNS_GENERIC_VALIDATION_ERROR_MESSAGE]})
