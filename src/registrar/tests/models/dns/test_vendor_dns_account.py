from django.test import TestCase
from django.db import IntegrityError, transaction

from registrar.models.dns.dns_vendor import DnsVendor
from registrar.models.dns.vendor_dns_account import VendorDnsAccount


class VendorDnsAccountTest(TestCase):
    def setUp(self):
        self.vendor = DnsVendor.objects.get(name=DnsVendor.CF)
        self.vendor_dns_account = VendorDnsAccount.objects.create(
            dns_vendor=self.vendor,
            x_account_id="12345",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
        )

    def tearDown(self):
        VendorDnsAccount.objects.all().delete()
        DnsVendor.objects.all().delete()

    def test_unique_x_account_id_per_vendor(self):
        """External account ids should be unique within the same vendor."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VendorDnsAccount.objects.create(
                    x_account_id=self.vendor_dns_account.x_account_id, dns_vendor=self.vendor
                )
