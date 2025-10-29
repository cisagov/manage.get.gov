from django.test import TestCase
from django.db import IntegrityError, transaction
from registrar.models import (
    Domain,
    DnsAccount,
    DnsZone,
    DnsRecord,
    VendorDnsRecord,
    DnsRecord_VendorDnsRecord
)

class DnsRecordVendorDnsRecordTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dns_domain = Domain.objects.create(name="dns-test.gov")
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_zone = DnsZone.objects.create(dns_account=self.dns_account, domain=self.dns_domain)
        self.dns_record = DnsRecord.objects.create(dns_zone=self.dns_zone)
        self.vendor_dns_record = VendorDnsRecord.objects.create(
            x_record_id="1",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
        )
        self.dns_record_vendor_dns_record = DnsRecord_VendorDnsRecord.objects.create(
            dns_record=self.dns_record,
            vendor_dns_record=self.vendor_dns_record,
            is_active=True
        )

    def tearDown(self):
        super().tearDown()
        DnsAccount.objects.all().delete()
        DnsZone.objects.all().delete()
        DnsRecord.objects.all().delete()
        Domain.objects.all().delete()
        VendorDnsRecord.objects.all().delete()
        DnsRecord_VendorDnsRecord.objects.all().delete()

    def test_dns_zone_vendor_dns_zone_is_active_constraint_throws_error(self):
        """ "Only allow 1 active vendor per DNS zone."""
        vendor_record_2 = VendorDnsRecord.objects.create(
            x_record_id="2",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DnsRecord_VendorDnsRecord.objects.create(
                    dns_record=self.dns_record,
                    vendor_dns_record=vendor_record_2,
                    is_active=True
                )
