from django.test import TestCase
from registrar.models import Domain, DnsAccount, DnsZone, DnsRecord
from registrar.validations import (
    DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE,
    DNS_NAME_HYPHEN_ERROR_MESSAGE,
)


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

    # --- DNS name validation tests for model ---

    def test_dns_record_name_with_consecutive_dots_raises(self):
        """DNS record name with consecutive dots should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="test..dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn(DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE, str(ctx.exception))

    def test_dns_record_name_with_leading_dot_raises(self):
        """DNS record name with leading dot should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name=".test.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn(DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE, str(ctx.exception))

    def test_dns_record_name_with_trailing_dot_raises(self):
        """DNS record name with trailing dot should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="test.dns-test.gov.",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn(DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE, str(ctx.exception))

    def test_dns_record_name_with_hyphen_at_start_of_label_raises(self):
        """DNS record name with hyphen at start of label should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="-test.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn(DNS_NAME_HYPHEN_ERROR_MESSAGE, str(ctx.exception))

    def test_dns_record_name_with_hyphen_at_end_of_label_raises(self):
        """DNS record name with hyphen at end of label should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="test-.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn(DNS_NAME_HYPHEN_ERROR_MESSAGE, str(ctx.exception))

    def test_dns_record_name_exceeds_per_label_limit_raises(self):
        """DNS record name with a label exceeding 63 characters should fail validation."""
        from django.core.exceptions import ValidationError

        long_label = "a" * 64
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name=f"{long_label}.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_dns_record_name_exceeds_total_fqdn_limit_raises(self):
        """A name whose labels are each within 63 chars but whose total exceeds 253 should fail."""
        from django.core.exceptions import ValidationError

        # 4 labels of 63 + 3 dots = 255 chars — every label is valid, only the total exceeds 253.
        long_name = ".".join(["a" * 63] * 4)
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name=long_name,
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_dns_record_name_at_253_total_with_valid_labels_passes(self):
        """A name at exactly 253 chars total with every label within 63 chars should pass."""
        # 3 labels of 63 + 1 label of 61 + 3 dots = 253 chars — boundary value, all labels valid.
        name_at_limit = ".".join(["a" * 63, "a" * 63, "a" * 63, "a" * 61])
        self.assertEqual(len(name_at_limit), 253)
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name=name_at_limit,
            ttl=3600,
            content="192.0.2.1",
        )
        record.full_clean()  # should not raise

    def test_dns_record_name_with_invalid_character_raises(self):
        """DNS record name with invalid character should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="test(invalid).dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_dns_record_name_wildcard_valid(self):
        """DNS record with wildcard as first label should be valid."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="*.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        record.clean()  # should not raise

    def test_dns_record_name_with_spaces_raises(self):
        """DNS record name with spaces should fail validation."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="test example.dns-test.gov",
            ttl=3600,
            content="192.0.2.1",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_dns_record_name_apex_valid(self):
        """DNS record name with @ (apex) should be valid."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="@",
            ttl=3600,
            content="192.0.2.1",
        )
        record.clean()  # should not raise

    def test_dns_record_name_normalized_to_lowercase_on_clean(self):
        """Mixed-case names are lowercased during clean()."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="TEST.Dns-Test.Gov",
            ttl=3600,
            content="192.0.2.1",
        )
        record.clean()
        self.assertEqual(record.name, "test.dns-test.gov")

    def test_dns_record_name_normalized_to_lowercase_on_save(self):
        """Mixed-case names are lowercased before storage, even when save() is called directly."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="TEST.Dns-Test.Gov",
            ttl=3600,
            content="192.0.2.1",
        )
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.name, "test.dns-test.gov")
