from django.test import TestCase
from django.db import IntegrityError, transaction
from registrar.models import Domain, DnsAccount, DnsZone, DnsVendor, VendorDnsZone, DnsZone_VendorDnsZone


class DnsZoneVendorDnsZoneTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dns_domain, _ = Domain.objects.get_or_create(name="dns-test.gov")
        self.dns_account, _ = DnsAccount.objects.get_or_create(name="acct-base")
        self.dns_zone, _ = DnsZone.objects.get_or_create(dns_account=self.dns_account, domain=self.dns_domain)
        self.dns_vendor, _ = DnsVendor.objects.get_or_create(name="Cloudflare")
        self.vendor_dns_zone, _ = VendorDnsZone.objects.get_or_create(
            x_zone_id="1",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
        )
        self.dns_zone_vendor_dns_zone, _ = DnsZone_VendorDnsZone.objects.get_or_create(
            dns_zone=self.dns_zone, vendor_dns_zone=self.vendor_dns_zone, is_active=True
        )

    def tearDown(self):
        super().tearDown()
        DnsAccount.objects.all().delete()
        DnsZone.objects.all().delete()
        Domain.objects.all().delete()
        DnsVendor.objects.all().delete()
        DnsZone_VendorDnsZone.objects.all().delete()

    def test_dns_zone_vendor_dns_zone_is_active_constraint_throws_error(self):
        """ "Only allow 1 active vendor per DNS zone."""
        vendor_zone_2, _ = VendorDnsZone.objects.get_or_create(
            x_zone_id="2",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DnsZone_VendorDnsZone.objects.get_or_create(
                    dns_zone=self.dns_zone, vendor_dns_zone=vendor_zone_2, is_active=True
                )
