from django.test import TestCase
from registrar.models import Domain, DnsAccount, DnsZone, DnsRecord


class DnsRecordTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dns_domain = Domain.objects.create(name="dns-test.gov")
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_zone = DnsZone.objects.create(dns_account=self.dns_account, domain=self.dns_domain)
        self.dns_record = DnsRecord.objects.create(dns_zone=self.dns_zone)

    def tearDown(self):
        super().tearDown()
        DnsAccount.objects.all().delete()
        DnsZone.objects.all().delete()
        Domain.objects.all().delete()
        DnsRecord.objects.all().delete()

    def test_update_dns_record_success(self):
        """Update DNS A record content."""
        self.dns_record.content = "1.1.1.1"
        self.dns_record.save()

    def test_delete_dns_record_success(self):
        """Delete DNS record."""
        outdated_record = DnsRecord.objects.create(dns_zone=self.dns_zone)
        DnsRecord.objects.filter(id=outdated_record.id).delete()
