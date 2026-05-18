from django.test import TestCase
from registrar.models import Domain, DnsAccount, DnsZone, DnsRecord
from registrar.validations import (
    DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE,
    DNS_NAME_HYPHEN_ERROR_MESSAGE,
    DNS_NAME_LEADING_TRAILING_DOT_ERROR_MESSAGE,
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

    # --- name normalization + _name_q equivalence tests ---

    def test_full_clean_normalizes_name_before_validation(self):
        """Mixed-case names are lowercased by full_clean before anything else runs."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="WWW.Dns-Test.Gov",
            ttl=3600,
            content="192.0.2.1",
        )
        record.full_clean()
        self.assertEqual(record.name, "www.dns-test.gov")

    def test_save_normalizes_name_when_full_clean_bypassed(self):
        """Direct save() without full_clean still lowercases the stored name."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="A",
            name="WWW",
            ttl=3600,
            content="192.0.2.1",
        )
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.name, "www")

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
        self.assertIn(DNS_NAME_LEADING_TRAILING_DOT_ERROR_MESSAGE, str(ctx.exception))

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
        self.assertIn(DNS_NAME_LEADING_TRAILING_DOT_ERROR_MESSAGE, str(ctx.exception))

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

    def test_name_q_at_symbol_matches_bare_domain(self):
        """A query for '@' (root of the zone) matches records stored as the bare domain name."""
        DnsRecord.objects.create(dns_zone=self.dns_zone, type="A", name="dns-test.gov", ttl=3600, content="192.0.2.1")
        matches = DnsRecord.objects.filter(DnsRecord._name_q("@", "dns-test.gov"))
        self.assertEqual(matches.count(), 1)

    def test_name_q_bare_domain_matches_at_symbol(self):
        """A query for the bare domain matches records stored as '@'."""
        DnsRecord.objects.create(dns_zone=self.dns_zone, type="A", name="@", ttl=3600, content="192.0.2.1")
        matches = DnsRecord.objects.filter(DnsRecord._name_q("dns-test.gov", "dns-test.gov"))
        self.assertEqual(matches.count(), 1)

    def test_name_q_label_matches_fqdn(self):
        """A query for a bare label matches records stored as the FQDN."""
        DnsRecord.objects.create(
            dns_zone=self.dns_zone, type="A", name="www.dns-test.gov", ttl=3600, content="192.0.2.1"
        )
        matches = DnsRecord.objects.filter(DnsRecord._name_q("www", "dns-test.gov"))
        self.assertEqual(matches.count(), 1)

    def test_name_q_fqdn_matches_label(self):
        """A query for an FQDN matches records stored as the bare label."""
        DnsRecord.objects.create(dns_zone=self.dns_zone, type="A", name="www", ttl=3600, content="192.0.2.1")
        matches = DnsRecord.objects.filter(DnsRecord._name_q("www.dns-test.gov", "dns-test.gov"))
        self.assertEqual(matches.count(), 1)

    # --- CNAME name != hostname model-level validation tests ---

    def test_clean_cname_name_matches_content_fqdn_raises(self):
        """CNAME record whose FQDN name equals its content should fail clean()."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="CNAME",
            name="sub.dns-test.gov",
            ttl=3600,
            content="sub.dns-test.gov",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_clean_cname_bare_label_expands_to_match_content_raises(self):
        """CNAME record with a bare label name that expands to match content should fail clean().

        A bare label "sub" in dns-test.gov zone expands to "sub.dns-test.gov"; if content
        is "sub.dns-test.gov" this should be caught even though the stored name is the label.
        """
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="CNAME",
            name="sub",
            ttl=3600,
            content="sub.dns-test.gov",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_clean_cname_at_symbol_expands_to_match_content_raises(self):
        """CNAME record with '@' (root) that expands to match content should fail clean().

        '@' in dns-test.gov zone expands to "dns-test.gov"; if content is "dns-test.gov"
        this should be caught even though the stored name is '@'.
        """
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="CNAME",
            name="@",
            ttl=3600,
            content="dns-test.gov",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_clean_cname_name_differs_from_content_valid(self):
        """CNAME record whose name does not resolve to the same value as content should pass."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="CNAME",
            name="sub.dns-test.gov",
            ttl=3600,
            content="other.example.gov",
        )
        record.clean()  # should not raise

    def test_clean_cname_no_content_skips_hostname_check(self):
        """CNAME record with no content should not trigger the hostname check."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="CNAME",
            name="sub.dns-test.gov",
            ttl=3600,
            content=None,
        )
        record.clean()  # should not raise

    def test_clean_non_cname_record_skips_hostname_check(self):
        """Non-CNAME records should not be subject to the name != hostname validation."""
        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="TXT",
            name="dns-test.gov",
            ttl=3600,
            content="dns-test.gov",
        )
        record.clean()  # should not raise — TXT records can have name == content

    def test_clean_cname_bare_label_matches_content_case_insensitive_raises(self):
        """A CNAME whose name and content differ only in letter case should still fail.
        DNS names are not case-sensitive, so 'www' pointing to 'Www.dns-test.gov' is
        the same as pointing to itself."""
        from django.core.exceptions import ValidationError

        record = DnsRecord(
            dns_zone=self.dns_zone,
            type="CNAME",
            name="www",
            ttl=3600,
            content="Www.dns-test.gov",
        )
        with self.assertRaises(ValidationError) as ctx:
            record.clean()
        self.assertIn("name", ctx.exception.message_dict)
