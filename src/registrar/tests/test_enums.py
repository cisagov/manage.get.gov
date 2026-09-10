from django.test import SimpleTestCase

from registrar.utility.enums import DNS_TTL_CHOICES, format_dns_ttl


class TestFormatDnsTtl(SimpleTestCase):
    def test_known_ttl_values_use_form_notation(self):
        for ttl, expected_label in DNS_TTL_CHOICES:
            with self.subTest(ttl=ttl):
                self.assertEqual(format_dns_ttl(ttl), expected_label)

    def test_unknown_ttl_values_fall_back_to_seconds(self):
        # 1 is the DnsRecord model default (and Cloudflare's "automatic" TTL);
        # 120/600 pass DnsRecord._validate_ttl (60-86400) and can arrive via
        # vendor sync, which bypasses the form's choices. None of these may crash.
        self.assertEqual(format_dns_ttl(1), "1 second")
        self.assertEqual(format_dns_ttl(120), "120 seconds")
        self.assertEqual(format_dns_ttl(600), "600 seconds")
