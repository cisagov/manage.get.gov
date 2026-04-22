"""Unit tests for the DnsOperationLog audit trail used by analysts/admins.

Prototype scope — proves the helper writes the row shape that the admin
surface depends on. See docs/developer/dns-error-handling.md §12.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from registrar.models.dns.dns_operation_log import DnsOperationLog
from registrar.utility.dns_operation_log import record_dns_operation


class TestRecordDnsOperation(TestCase):
    def _fake_request(self, request_id="req-xyz", user_email="analyst@test.gov"):
        user = SimpleNamespace(is_authenticated=True, email=user_email)
        return SimpleNamespace(_dns_request_id=request_id, user=user)

    def test_success_row_is_written_with_expected_fields(self):
        record_dns_operation(
            request=self._fake_request(),
            operation="create_dns_record",
            outcome="success",
            domain_name="igorville.gov",
            zone_id="zone-1",
            record_id="rec-1",
        )
        row = DnsOperationLog.objects.get()
        self.assertEqual(row.operation, "create_dns_record")
        self.assertEqual(row.outcome, "success")
        self.assertEqual(row.domain_name, "igorville.gov")
        self.assertEqual(row.zone_id, "zone-1")
        self.assertEqual(row.record_id, "rec-1")
        self.assertEqual(row.request_id, "req-xyz")
        self.assertEqual(row.user_email, "analyst@test.gov")

    def test_failure_row_captures_error_code_and_cf_ray(self):
        record_dns_operation(
            request=self._fake_request(),
            operation="create_dns_record",
            outcome="failure",
            domain_name="igorville.gov",
            zone_id="zone-missing",
            error_code="DNS_ZONE_NOT_FOUND",
            upstream_status=404,
            cf_ray="ray-abc-123",
            notes="zone not found in cloudflare",
        )
        row = DnsOperationLog.objects.get()
        self.assertEqual(row.outcome, "failure")
        self.assertEqual(row.error_code, "DNS_ZONE_NOT_FOUND")
        self.assertEqual(row.upstream_status, 404)
        self.assertEqual(row.cf_ray, "ray-abc-123")
        self.assertIn("zone not found", row.notes)

    def test_enroll_domain_row(self):
        record_dns_operation(
            request=self._fake_request(),
            operation="enroll_domain",
            outcome="success",
            domain_name="newdomain.gov",
        )
        row = DnsOperationLog.objects.get()
        self.assertEqual(row.operation, "enroll_domain")
        self.assertEqual(row.outcome, "success")
        self.assertEqual(row.domain_name, "newdomain.gov")

    def test_anonymous_user_results_in_empty_user_email(self):
        anon = SimpleNamespace(is_authenticated=False)
        request = SimpleNamespace(_dns_request_id="req-1", user=anon)
        record_dns_operation(request=request, operation="enroll_domain", outcome="success", domain_name="x.gov")
        row = DnsOperationLog.objects.get()
        self.assertEqual(row.user_email, "")
        self.assertEqual(row.request_id, "req-1")

    def test_missing_request_object_still_writes_row(self):
        record_dns_operation(operation="enroll_domain", outcome="success", domain_name="x.gov")
        row = DnsOperationLog.objects.get()
        self.assertEqual(row.request_id, "")
        self.assertEqual(row.user_email, "")

    def test_db_error_is_swallowed_and_logged(self):
        """A broken audit write must not propagate and break the user's DNS flow."""
        with patch.object(DnsOperationLog.objects, "create", side_effect=RuntimeError("boom")):
            # Must not raise.
            record_dns_operation(operation="create_dns_record", outcome="success", domain_name="x.gov")
        self.assertEqual(DnsOperationLog.objects.count(), 0)
