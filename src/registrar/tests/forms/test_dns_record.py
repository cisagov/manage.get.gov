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

    def make_form(self, data):
        record = DnsRecord(dns_zone=self.zone)
        return DomainDNSRecordForm(
            data=data,
            instance=record,
        )

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
            self.assertEqual(form.errors["name"], ["Enter the name of this record."])

    def test_invalid_dns_name_throws_error(self):
        # Testing invalid first character
        self.assert_dns_name_errors("1bc", ["Enter a name that begins with a letter and ends with a letter or number."])

        # Testing invalid last character
        self.assert_dns_name_errors("abc-", ["Enter a name that begins with a letter and ends with a letter or number."])

        # Testing invalid character and invalid last character
        self.assert_dns_name_errors(
            "ab$c", ["Enter a name using only letters, numbers, hyphens, periods, or the @ symbol."]
        )

        self.assert_dns_name_errors("a" * 64, ["Name must be no more than 63 characters."])

        # Testing space in name
        self.assert_dns_name_errors("ab cd", ["Enter the DNS name without any spaces."])

    def test_dns_record_with_invalid_content_throws_error(self):
        invalid_content_by_type = {
            "A": "2008:db8:1234:5678",
            "AAAA": "192.0.2.10",
        }
        invalid_quotes_txt_error = (
            'Record content is not quoted correctly; ensure it begins and ends with double quotes(").'
        )
        for record_type, bad_content in invalid_content_by_type.items():
            with self.subTest(record_type=record_type):
                data = self.valid_form_data_for_record_type(record_type, bad_content)
                form = self.make_form(data)

                self.assertFalse(form.is_valid())
                self.assertIn(
                    DNSRecordTypes(record_type).error_message or invalid_quotes_txt_error, form.errors["content"]
                )

    def test_dns_record_with_blank_content_throws_error(self):
        empty_txt_message = "Enter the content for this record."
        for record_type, content in self.VALID_CONTENT_BY_TYPE.items():
            with self.subTest(record_type=record_type):
                priority = 10 if record_type == "MX" else None
                data = self.valid_form_data_for_record_type(record_type, content, priority=priority)
                data["content"] = ""
                form = self.make_form(data)

                self.assertFalse(form.is_valid())
                self.assertIn(DNSRecordTypes(record_type).error_message, form.errors["content"])

    def test_valid_mx_record_form_success(self):
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov", priority=10)
        form = self.make_form(data)
        self.assertTrue(form.is_valid())

    def test_mx_record_without_priority_throws_error(self):
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov")
        form = self.make_form(data)
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)
        self.assertIn("Enter a priority for this record.", form.errors["priority"])

    def test_mx_record_priority_below_minimum_throws_error(self):
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov", priority=-1)
        form = self.make_form(data)
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)
        self.assertIn("Enter a priority number between 0-65535.", form.errors["priority"])

    def test_mx_record_priority_above_maximum_throws_error(self):
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov", priority=65536)
        form = self.make_form(data)
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

    def test_mx_record_name_with_space_throws_mx_specific_error(self):
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov", priority=10)
        data["name"] = "my name"
        form = self.make_form(data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("Enter the name you want without any spaces.", form.errors["name"])

    def test_mx_record_with_space_in_content_throws_error(self):
        data = self.valid_form_data_for_record_type("MX", "invalid hostname", priority=10)
        form = self.make_form(data)
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)
        self.assertIn("Enter the mail server without any spaces.", form.errors["content"])

    def test_mx_record_with_content_too_long_throws_error(self):
        data = self.valid_form_data_for_record_type("MX", "a" * 254, priority=10)
        form = self.make_form(data)
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)
        self.assertIn("Name must be no more than 253 characters.", form.errors["content"])

    def test_duplicate_name_among_a_aaaa_cname_throws_error(self):
        """A, AAAA, and CNAME records cannot share a name within the same zone."""
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="www",
            ttl=3600,
            content="192.0.2.1",
        )

        for record_type, content in [("A", "192.0.2.2"), ("AAAA", "2001:db8::1"), ("CNAME", "alias.example.gov")]:
            with self.subTest(record_type=record_type):
                data = self.valid_form_data_for_record_type(record_type, content)
                form = self.make_form(data)
                self.assertFalse(form.is_valid())
                self.assertIn("name", form.errors)
                self.assertIn("A record with that name already exists. Names must be unique.", form.errors["name"])

    def test_duplicate_name_does_not_apply_to_mx(self):
        """MX records are not subject to the A/AAAA/CNAME name uniqueness constraint."""
        DnsRecord.objects.create(
            dns_zone=self.zone,
            type=DNSRecordTypes.A,
            name="www",
            ttl=3600,
            content="192.0.2.1",
        )
        data = self.valid_form_data_for_record_type("MX", "mail.example.gov", priority=10)
        data["name"] = "www"
        form = self.make_form(data)
        self.assertTrue(form.is_valid())
