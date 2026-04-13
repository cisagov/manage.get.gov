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

    # --- clean() validation tests ---

    def test_clean_a_records_same_name_allowed(self):
        """Two A records with the same name in the same zone should not conflict."""
        DnsRecord.objects.create(
            dns_zone=self.dns_zone,
            type="A",
            name="test.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="test.dns-test.gov",
            ttl=3600,
            content="192.0.2.2",
        )
        record.clean()  # should not raise

    def test_clean_a_and_aaaa_same_name_allowed(self):
        """An A record and AAAA record with the same name should not conflict."""
        DnsRecord.objects.create(
            dns_zone=self.dns_zone,
            type="A",
            name="test.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="AAAA",
            name="test.dns-test.gov",
            ttl=3600,
            content="2001:db8::1",
        )
        record.clean()  # should not raise

    def test_clean_a_and_cname_same_name_raises(self):
        """An A record cannot share a name with an existing CNAME record."""
        from django.core.exceptions import ValidationError

        DnsRecord.objects.create(
            dns_zone=self.dns_zone,
            type="CNAME",
            name="test.dns-test.gov",
            ttl=3600,
            content="example.gov",
        )
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="test.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_clean_mx_without_priority_raises(self):
        """An MX record with no priority should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="MX",
            name="dns-test.gov",
            ttl=3600,
            content="mail.example.gov",
            priority=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            record.clean()
        self.assertIn("priority", ctx.exception.message_dict)

    def test_clean_mx_with_priority_valid(self):
        """An MX record with a valid priority should pass validation."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="MX",
            name="dns-test.gov",
            ttl=3600,
            content="mail.example.gov",
            priority=10,
        )
        record.clean()  # should not raise
