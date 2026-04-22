"""Tests for the admin-editable DNS error message store.

Prototype scope — proves the DB-hit path, the fallback path, and the signal-
driven cache invalidation. See docs/developer/dns-error-handling.md
§17.

Note: migration 0180 seeds rows for every DnsHostingErrorCodes entry, so tests
use update_or_create and then rely on transactional rollback (Django TestCase)
to leave the seeded data pristine between runs.
"""

from django.test import TestCase

from registrar.models.dns.dns_error_message import DnsErrorMessage
from registrar.utility import messages as messages_util
from registrar.utility.errors import DnsNotFoundError


class TestGetUserMessage(TestCase):
    def setUp(self):
        messages_util.invalidate_cache()

    def test_returns_admin_edited_text_when_row_exists(self):
        DnsErrorMessage.objects.update_or_create(
            namespace="dns",
            code="ZONE_NOT_FOUND",
            defaults={"message": "Custom admin-edited copy."},
        )
        messages_util.invalidate_cache()
        self.assertEqual(messages_util.get_user_message("dns", "ZONE_NOT_FOUND"), "Custom admin-edited copy.")

    def test_returns_none_when_row_missing(self):
        self.assertIsNone(messages_util.get_user_message("dns", "NEVER_SEEDED"))

    def test_post_save_signal_invalidates_cache(self):
        row, _ = DnsErrorMessage.objects.update_or_create(
            namespace="dns",
            code="ZONE_NOT_FOUND",
            defaults={"message": "Original copy."},
        )
        # Prime the cache.
        self.assertEqual(messages_util.get_user_message("dns", "ZONE_NOT_FOUND"), "Original copy.")

        row.message = "Updated copy."
        row.save()

        # Signal fires → cache invalidated → next read hits the DB again.
        self.assertEqual(messages_util.get_user_message("dns", "ZONE_NOT_FOUND"), "Updated copy.")


class TestDnsHostingErrorMessageResolution(TestCase):
    """DnsHostingError.message prefers DB row, falls back to _error_mapping."""

    def setUp(self):
        messages_util.invalidate_cache()

    def test_uses_db_row_when_present(self):
        DnsErrorMessage.objects.update_or_create(
            namespace="dns",
            code="ZONE_NOT_FOUND",
            defaults={"message": "Zone is not enrolled — edited by product."},
        )
        messages_util.invalidate_cache()
        exc = DnsNotFoundError()
        self.assertEqual(exc.message, "Zone is not enrolled — edited by product.")

    def test_falls_back_to_error_mapping_when_no_row(self):
        # Remove the seeded row to exercise the fallback path.
        DnsErrorMessage.objects.filter(namespace="dns", code="ZONE_NOT_FOUND").delete()
        messages_util.invalidate_cache()
        exc = DnsNotFoundError()
        # Fallback value from _error_mapping.
        self.assertIn("DNS zone", exc.message)

    def test_explicit_message_wins_over_db_and_mapping(self):
        DnsErrorMessage.objects.update_or_create(
            namespace="dns", code="ZONE_NOT_FOUND", defaults={"message": "from DB"}
        )
        messages_util.invalidate_cache()
        exc = DnsNotFoundError(message="explicit-at-construction")
        self.assertEqual(exc.message, "explicit-at-construction")
