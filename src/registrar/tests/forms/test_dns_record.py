from django.test import TestCase
from django.core.exceptions import ValidationError

from registrar.forms.domain import DomainDNSRecordForm
from registrar.models import Domain, DnsAccount, DnsZone, DnsRecord


class BaseDomainDNSRecordFormTest(TestCase):
    def setUp(self):
        self.domain = Domain.objects.create(name="example.gov")
        self.account = DnsAccount.objects.create(name="acct-base")
        self.zone = DnsZone.objects.create(
            dns_account=self.account,
            domain=self.domain,
        )
    
    def valid_form_data_for_a_record(self):
        return {
            "type_field": "A",
            "name": "www",
            "content": "1.1.1.1",
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
        """
        data = self.valid_form_data_for_a_record()
        data["name"] = name_value

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

        for message in expected_messages:
            self.assertIn(message, form.errors["name"])
    

class DomainDNSRecordFormValidationTests(BaseDomainDNSRecordFormTest):
    
    def test_valid_dns_record_form_success(self):
        data = self.valid_form_data_for_a_record()
        form = self.make_form(data)
        self.assertTrue(form.is_valid())

        print("form.errors===", form.errors)
    
    def test_blank_dns_name_throws_error(self):
        data = self.valid_form_data_for_a_record()
        data["name"] = ""

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertEqual(
            form.errors["name"],
            ["This field is required."]
        )
    
    def test_invalid_dns_name_throws_error(self):
        # Testing invalid first character
        self.assert_dns_name_errors(
            "1bc",
            [
                "Enter a name that begins with a letter and ends with a letter or digit."
            ]
        )
        
        # Testing invalid last character
        self.assert_dns_name_errors(
            "abc-",
            [
                "Enter a name that begins with a letter and ends with a letter or digit."
            ]
        )
        
        # Testing invalid character and invalid last character
        self.assert_dns_name_errors(
            "ab$c",
            [
                "Enter a name using only letters, numbers, hyphens, periods, or the @ symbol."
            ]
        )

        self.assert_dns_name_errors(
            "a" * 64,
            [
                "Name must be no more than 63 characters."
            ]
        )
    
    def test_dns_a_record_with_invalid_ipv4_address_throws_error(self):
        data = self.valid_form_data_for_a_record()
        data["content"] = "1000.1.1.1"

        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("Enter a valid IPv4 address.", form.errors["content"])
    
    def test_dns_a_record_with_blank_ipv4_address_throws_error(self):
        data = self.valid_form_data_for_a_record()
        data["content"] = ""
        
        form = self.make_form(data)

        self.assertFalse(form.is_valid())
        self.assertIn("IPv4 address is required.", form.errors["content"])