"""Regression tests for the DNS-zone nameserver count constraint."""

from django import forms
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from registrar.models.dns.dns_zone import DnsZone


class DnsZoneNameserversForm(forms.ModelForm):
    """Exercise model validation without unrelated relation fields."""

    class Meta:
        model = DnsZone
        fields = ["nameservers"]


class DnsZoneNameserverValidationTests(SimpleTestCase):
    """Reject incomplete nameserver sets through both model and form validation."""

    def test_clean_rejects_fewer_than_two_nameservers(self):
        for nameservers in ([], ["ns1.example.org"]):
            with self.subTest(nameservers=nameservers):
                # Avoid the unrelated database-backed default SOA lookup.
                zone = DnsZone(soa_id=1, nameservers=nameservers)
                with self.assertRaises(ValidationError) as caught:
                    zone.clean()
                self.assertEqual(
                    caught.exception.message_dict,
                    {"nameservers": ["DNS zone must have at least 2 nameservers."]},
                )

    def test_clean_accepts_two_or_more_nameservers(self):
        for count in (2, 3):
            with self.subTest(count=count):
                nameservers = [f"ns{index}.example.org" for index in range(1, count + 1)]
                self.assertIsNone(DnsZone(soa_id=1, nameservers=nameservers).clean())

    def test_form_rejects_fewer_than_two_nameservers(self):
        for nameservers in ("", "ns1.example.org"):
            with self.subTest(nameservers=nameservers):
                form = DnsZoneNameserversForm(data={"nameservers": nameservers}, instance=DnsZone(soa_id=1))
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors["nameservers"], ["DNS zone must have at least 2 nameservers."])

    def test_form_accepts_two_or_more_nameservers(self):
        for count in (2, 3):
            with self.subTest(count=count):
                nameservers = ",".join(f"ns{index}.example.org" for index in range(1, count + 1))
                form = DnsZoneNameserversForm(data={"nameservers": nameservers}, instance=DnsZone(soa_id=1))
                self.assertTrue(form.is_valid(), form.errors)
