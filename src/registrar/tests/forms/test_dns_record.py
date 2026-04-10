from django.test import TestCase

from registrar.forms.domain import DomainDNSRecordForm
from registrar.models import Domain, DnsAccount, DnsZone, DnsRecord
from registrar.utility.enums import DNSRecordTypes
from faker import Faker

fake = Faker()


class BaseDomainDNSRecordFormTest(TestCase):
    def setUp(self):
        self.domain = Domain.objects.create(name="example.gov")
        self.account = DnsAccount.objects.create(name="acct-base")
        self.zone = DnsZone.objects.create(
            dns_account=self.account,
            domain=self.domain,
        )
        self.VALID_CONTENT_BY_TYPE = {
            "A": "192.0.2.10",
            "AAAA": "2001:db8::1234:5678",
            "MX": "mail.example.gov",
            # TODO: Comment out CNAME test case after implementing CNAME host name validation
            # "CNAME": "www.example.com",
            # TODO: Comment out PTR test case after implementing PTR host name validation
            # "PTR": "www.example.com",
            "TXT": "Some valid text",
        }

    def valid_form_data_for_record_type(self, record_type, content, priority=None):
        data = {
            "type": record_type,
            "name": "www",
            "content": content,
            "ttl": 300,
            "comment": "testing comment",
        }
        if priority is not None:
            data["priority"] = priority
        return data

    def make_form(self, data, domain_name=None):
        record = DnsRecord(dns_zone=self.zone)
        kwargs = {"data": data, "instance": record}
        if domain_name:
            kwargs["domain_name"] = domain_name
        return DomainDNSRecordForm(**kwargs)

    def assert_dns_name_errors(self, name_value, expected_messages):
        """
        Helper to assert DNS name errors are raised from validate_dns_name in validations.py

        This method uses only A type records rather than iterating over multiple record types,
        since the name validations are shared between each record type.
        """
        data = self.valid_form_data_for_record_type("A", self.VALID_CONTENT_BY_TYPE["A"])
        data["name"] = name_value

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

        for message in expected_messages:
            self.assertIn(message, form.errors["name"])


class DomainDNSRecordFormValidationTests(BaseDomainDNSRecordFormTest):

    def setUp(self):
        super().setUp()
        self.forms_data = [
            self.valid_form_data_for_record_type(record_type, content, priority=10 if record_type == "MX" else None)
            for record_type, content in self.VALID_CONTENT_BY_TYPE.items()
        ]

    def test_valid_dns_record_form_success(self):
        for data in self.forms_data:
            form = self.make_form(data)
            self.assertTrue(form.is_valid())

    def test_blank_dns_name_throws_error(self):
        for data in self.forms_data:
            data["name"] = ""

            form = self.make_form(data)

            self.assertFalse(form.is_valid())
            self.assertIn("name", form.errors)
            self.assertEqual(form.errors["name"], ["Enter a name for this record."])

    def test_invalid_dns_name_throws_error(self):
        # Testing invalid first character
        self.assert_dns_name_errors("1bc", ["Enter a name that begins with a letter and ends with a letter or number."])

        # Testing invalid last character
        self.assert_dns_name_errors(
            "abc-", ["Enter a name that begins with a letter and ends with a letter or number."]
        )

        # Testing invalid character and invalid last character
        self.assert_dns_name_errors(
            "ab$c", ["Enter a name using only letters, numbers, hyphens, periods, or the @ symbol."]
        )

        self.assert_dns_name_errors("a" * 64, ["Name must be no more than 63 characters."])

        # Testing space in name
        self.assert_dns_name_errors("ab cd", ["Enter the DNS name without any spaces."])

    def test_dns_record_with_invalid_content_throws_error(self):
        invalid_content_by_type = {
            "A": ("2008:db8:1234:5678", "Enter a valid IPv4 address."),
            "AAAA": ("192.0.2.10", "Enter a valid IPv6 address."),
            # TODO: Comment out and complete CNAME test case when CNAME validation is implemented
            # "CNAME": "..."
            # TODO: Comment out and complete PTR test case when PTR validation is implemented
            # "PTR": "..."
        }
        for record_type, (bad_content, expected_error) in invalid_content_by_type.items():
            with self.subTest(record_type=record_type):
                data = self.valid_form_data_for_record_type(record_type, bad_content)
                form = self.make_form(data)

                self.assertFalse(form.is_valid())
                self.assertIn(expected_error, form.errors["content"])

    def test_dns_record_with_blank_content_throws_error(self):
        for record_type, content in self.VALID_CONTENT_BY_TYPE.items():
            with self.subTest(record_type=record_type):
                priority = 10 if record_type == "MX" else None
                data = self.valid_form_data_for_record_type(record_type, content, priority=priority)
                data["content"] = ""
                form = self.make_form(data)

                self.assertFalse(form.is_valid())
                # TXT doesn't have a predefined error_message in the enum, so just check an error exists
                if DNSRecordTypes(record_type).error_message:
                    self.assertIn(DNSRecordTypes(record_type).error_message, form.errors["content"])
                else:
                    self.assertIn("content", form.errors)


class DomainMXRecordFormTests(BaseDomainDNSRecordFormTest):
    """Tests for MX record-specific behavior in DomainDNSRecordForm."""

    def make_mx_form(self, content="mail.example.gov", priority=10, name="www", **overrides):
        data = self.valid_form_data_for_record_type("MX", content, priority=priority)
        data["name"] = name
        data.update(overrides)
        return self.make_form(data)

    # --- Valid cases ---

    def test_valid_mx_record_form_success(self):
        form = self.make_mx_form()
        self.assertTrue(form.is_valid())

    def test_valid_mx_record_with_root_name(self):
        """@ is a valid name for MX records."""
        form = self.make_mx_form(name="@")
        self.assertTrue(form.is_valid())

    def test_valid_mx_record_priority_at_minimum_boundary(self):
        form = self.make_mx_form(priority=0)
        self.assertTrue(form.is_valid())

    def test_valid_mx_record_priority_at_maximum_boundary(self):
        form = self.make_mx_form(priority=65535)
        self.assertTrue(form.is_valid())

    def test_valid_mx_record_content_at_max_length(self):
        """253-character hostname is the maximum allowed."""
        long_hostname = "a" * 249 + ".gov"
        form = self.make_mx_form(content=long_hostname)
        self.assertTrue(form.is_valid())

    # --- Priority validation ---

    def test_mx_record_without_priority_throws_error(self):
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov")
        form = self.make_form(data)
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)
        self.assertIn("Enter a priority for this record.", form.errors["priority"])

    def test_mx_record_priority_below_minimum_throws_error(self):
        form = self.make_mx_form(priority=-1)
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)
        self.assertIn("Enter a priority number between 0-65535.", form.errors["priority"])

    def test_mx_record_priority_above_maximum_throws_error(self):
        form = self.make_mx_form(priority=65536)
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)
        self.assertIn("Enter a priority number between 0-65535.", form.errors["priority"])

    def test_mx_record_priority_non_numeric_throws_error(self):
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov")
        data["priority"] = "notanumber"
        form = self.make_form(data)
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)
        self.assertIn("Enter a priority number between 0-65535.", form.errors["priority"])

    # --- Name validation ---

    def test_mx_record_name_with_space_throws_error(self):
        """MX records use the same DNS name validation as other record types."""
        form = self.make_mx_form(name="my name")
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("Enter the DNS name without any spaces.", form.errors["name"])

    # --- Content validation ---

    def test_mx_record_with_space_in_content_throws_error(self):
        form = self.make_mx_form(content="invalid hostname")
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)
        self.assertIn("Enter the mail server without any spaces.", form.errors["content"])

    def test_mx_record_with_content_too_long_throws_error(self):
        form = self.make_mx_form(content="a" * 254)
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)
        self.assertIn("Name must be no more than 253 characters.", form.errors["content"])

    def test_mx_record_with_blank_content_throws_error(self):
        form = self.make_mx_form(content="")
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)
        self.assertIn(DNSRecordTypes.MX.error_message, form.errors["content"])

    # --- Name uniqueness ---

    def test_duplicate_name_does_not_apply_to_mx(self):
        """MX records are not subject to the A/AAAA/CNAME name uniqueness constraint."""
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="www",
            ttl=3600,
            content="192.0.2.1",
        )
        form = self.make_mx_form(name="www")
        self.assertTrue(form.is_valid())


class DomainDNSRecordNameConflictTests(DomainMXRecordFormTests):
    """Tests for name field conflict validation in DomainDNSRecordForm."""

    def test_cname_conflicts_with_existing_a_record(self):
        """Creating a CNAME record with same name as existing A record should throw error."""
        # Create an existing A record
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="www",
            ttl=3600,
            content="192.0.2.1",
        )
        # Try to create a CNAME record with the same name
        data = self.valid_form_data_for_record_type("CNAME", "example.com")
        data["name"] = "www"
        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("A record with that name already exists", form.errors["name"][0])

    def test_cname_conflicts_with_existing_aaaa_record(self):
        """Creating a CNAME record with same name as existing AAAA record should throw error."""
        # Create an existing AAAA record
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.AAAA,
            name="www",
            ttl=3600,
            content="2001:db8::1",
        )
        # Try to create a CNAME record with the same name
        data = self.valid_form_data_for_record_type("CNAME", "example.com")
        data["name"] = "www"
        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("A record with that name already exists", form.errors["name"][0])

    def test_a_record_conflicts_with_existing_cname_record(self):
        """Creating an A record with same name as existing CNAME record should throw error."""
        # Create an existing CNAME record
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.CNAME,
            name="www",
            ttl=3600,
            content="example.com",
        )
        # Try to create an A record with the same name
        data = self.valid_form_data_for_record_type("A", "192.0.2.1")
        data["name"] = "www"
        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("A record with that name already exists", form.errors["name"][0])

    def test_aaaa_record_conflicts_with_existing_cname_record(self):
        """Creating an AAAA record with same name as existing CNAME record should throw error."""
        # Create an existing CNAME record
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.CNAME,
            name="www",
            ttl=3600,
            content="example.com",
        )
        # Try to create an AAAA record with the same name
        data = self.valid_form_data_for_record_type("AAAA", "2001:db8::1234:5678")
        data["name"] = "www"
        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("A record with that name already exists", form.errors["name"][0])

    def test_multiple_a_records_with_same_name_allowed(self):
        """Multiple A records with the same name should be allowed."""
        # Create an existing A record
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="www",
            ttl=3600,
            content="192.0.2.1",
        )
        # Create another A record with the same name but different content
        data = self.valid_form_data_for_record_type("A", "192.0.2.2")
        data["name"] = "www"
        form = self.make_form(data)

        self.assertTrue(form.is_valid())

    def test_mx_record_same_name_as_a_record_allowed(self):
        """MX records should be allowed with same name as A records."""
        # Create an existing A record
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="www",
            ttl=3600,
            content="192.0.2.1",
        )
        # MX records are not subject to name uniqueness constraints
        form = self.make_mx_form(name="www", priority=10)
        self.assertTrue(form.is_valid())

    def test_editing_cname_with_existing_a_record_name_throws_error(self):
        """Editing a record to have same name as existing A record should throw error."""
        # Create an existing A record
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="www",
            ttl=3600,
            content="192.0.2.1",
        )
        # Create a CNAME record with different name
        existing_cname = DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.CNAME,
            name="mail",
            ttl=3600,
            content="example.com",
        )
        # Try to edit it to have the same name as the A record
        data = self.valid_form_data_for_record_type("CNAME", "example.com")
        data["name"] = "www"
        form = self.make_form(data)
        form.instance = existing_cname

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_name_conflict_validation_with_domain_name_lookup(self):
        """Test name conflict detection when zone is looked up via domain_name (creating new record)."""
        # Create an existing A record in the zone
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="api",
            ttl=3600,
            content="192.0.2.1",
        )
        # Try to create a CNAME with same name, using domain_name lookup instead of instance.dns_zone
        # This simulates the form being used during new record creation (instance doesn't have dns_zone_id yet)
        data = self.valid_form_data_for_record_type("CNAME", "api.example.com")
        data["name"] = "api"

        record = DnsRecord()  # New record without dns_zone set
        form = DomainDNSRecordForm(
            data=data,
            instance=record,
            domain_name="example.gov",  # Zone will be looked up by domain name
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("A record with that name already exists", form.errors["name"][0])
