from django.test import TestCase
from registrar.models import Domain, DnsAccount, DnsZone, DnsSoa


class DnsZoneTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dns_domain, _ = Domain.objects.get_or_create(name="dns-test.gov")
        self.dns_account, _ = DnsAccount.objects.get_or_create(name="acct-base")
        self.dns_zone, _ = DnsZone.objects.get_or_create(dns_account=self.dns_account, domain=self.dns_domain)

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
