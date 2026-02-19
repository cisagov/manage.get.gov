from django.test import TestCase

from registrar.forms.domain import DomainDNSRecordForm
from registrar.models import Domain, DnsAccount, DnsZone, DnsRecord
from registrar.validations import RECORD_TYPE_VALIDATORS


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
        }

    def valid_form_data_for_record_type(self, record_type, content):
        return {
            "type": record_type,
            "name": "www",
            "content": content,
            "ttl": 300,
            "comment": "testing comment",
        }

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
            self.valid_form_data_for_record_type(record_type, content)
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
        self.assert_dns_name_errors("1bc", ["Enter a name that begins with a letter and ends with a letter or digit."])

        # Testing invalid last character
        self.assert_dns_name_errors("abc-", ["Enter a name that begins with a letter and ends with a letter or digit."])

        # Testing invalid character and invalid last character
        self.assert_dns_name_errors(
            "ab$c", ["Enter a name using only letters, numbers, hyphens, periods, or the @ symbol."]
        )

        self.assert_dns_name_errors("a" * 64, ["Name must be no more than 63 characters."])

    def test_dns_record_with_invalid_content_throws_error(self):
        invalid_content_by_type = {
            "A": "2008:db8:1234:5678",
            "AAAA": "192.0.2.10",
        }

        for record_type, bad_content in invalid_content_by_type.items():
            with self.subTest(record_type=record_type):
                data = self.valid_form_data_for_record_type(record_type, bad_content)
                form = self.make_form(data)

                self.assertFalse(form.is_valid())
                self.assertIn(RECORD_TYPE_VALIDATORS[record_type].error_message, form.errors["content"])

    def test_dns_record_with_blank_content_throws_error(self):
        for record_type, content in self.VALID_CONTENT_BY_TYPE.items():
            with self.subTest(record_type=record_type):
                data = self.valid_form_data_for_record_type(record_type, content)
                data["content"] = ""
                form = self.make_form(data)

                self.assertFalse(form.is_valid())
                self.assertIn(RECORD_TYPE_VALIDATORS[record_type].error_message, form.errors["content"])
