from django.test import TestCase
from registrar.models import Domain, DnsAccount, DnsZone, DnsSoa, VendorDnsZone, DnsZone_VendorDnsZone as ZonesJoin


class DnsZoneTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dns_domain = Domain.objects.create(name="dns-test.gov")
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_zone = DnsZone.objects.create(dns_account=self.dns_account, domain=self.dns_domain)

    def tearDown(self):
        super().tearDown()
        DnsAccount.objects.all().delete()
        DnsZone.objects.all().delete()
        Domain.objects.all().delete()

    def test_zone_defaults_name_to_domain(self):
        """Zones without a specified name will default set their name to their domain name."""
        self.assertEqual(self.dns_zone.name, self.dns_zone.domain.name)

    def test_zone_sets_default_soa(self):
        """Zones without a specified SOA will be assigned default SOA settings."""
        self.assertEqual(self.dns_zone.soa.pk, DnsSoa.get_default_pk())

    def test_set_zone_name(self):
        """Successfully change DNS Zone name."""
        updated_name = "subdomain.dns-test.gov"
        self.dns_zone.name = updated_name
        self.dns_zone.save()
        self.assertEqual(self.dns_zone.name, updated_name)

    def test_get_active_x_zone_id_success(self):
        x_zone_id = "56789abc"
        vendor_zone = VendorDnsZone.objects.create(
            x_zone_id=x_zone_id,
            x_created_at="2025-01-02T03:04:05Z",
            x_updated_at="2025-01-02T03:04:05Z",
        )

        ZonesJoin.objects.create(
            dns_zone=self.dns_zone,
            vendor_dns_zone=vendor_zone,
            is_active=True,
        )

        returned_x_zone_id = self.dns_zone.get_active_x_zone_id()
        self.assertEquals(returned_x_zone_id, x_zone_id)

    def test_get_active_x_zone_id_returns_none(self):
        x_zone_id = "56789abc"
        vendor_zone = VendorDnsZone.objects.create(
            x_zone_id=x_zone_id,
            x_created_at="2025-01-02T03:04:05Z",
            x_updated_at="2025-01-02T03:04:05Z",
        )

        ZonesJoin.objects.create(
            dns_zone=self.dns_zone,
            vendor_dns_zone=vendor_zone,
            is_active=False,
        )

        returned_x_zone_id = self.dns_zone.get_active_x_zone_id()
        self.assertIsNone(returned_x_zone_id)
