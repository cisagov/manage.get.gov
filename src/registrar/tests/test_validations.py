from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from registrar.validations import (
    DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE,
    DNS_NAME_FORMAT_ERROR_MESSAGE,
    DNS_NAME_HYPHEN_ERROR_MESSAGE,
    DNS_NAME_LENGTH_ERROR_MESSAGE,
    validate_dns_name,
)


class TestValidateDNSName(SimpleTestCase):
    def assert_dns_name_validation_error(self, name: str, expected_message: str) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_dns_name(name)

        self.assertEqual(ctx.exception.messages, [expected_message])

    def test_validate_dns_name_allows_empty_name(self):
        validate_dns_name("")

    def test_validate_dns_name_allows_apex_name(self):
        validate_dns_name("@")

    def test_validate_dns_name_accepts_valid_names(self):
        valid_names = ["www", "WWW", "my-domain", "sub.domain", "*", "*.service", "a*b", "sub.*"]

        for name in valid_names:
            with self.subTest(name=name):
                validate_dns_name(name)

    def test_validate_dns_name_rejects_names_with_spaces(self):
        self.assert_dns_name_validation_error("ab cd", "Enter the DNS name without any spaces.")

    def test_validate_dns_name_rejects_hyphen_at_label_boundary(self):
        for name in ["-abc", "abc-", "my.-domain", "my-.domain"]:
            with self.subTest(name=name):
                self.assert_dns_name_validation_error(name, DNS_NAME_HYPHEN_ERROR_MESSAGE)

    def test_validate_dns_name_rejects_consecutive_or_edge_dots(self):
        for name in ["ab..cd", ".abc", "abc."]:
            with self.subTest(name=name):
                self.assert_dns_name_validation_error(name, DNS_NAME_CONSECUTIVE_DOTS_ERROR_MESSAGE)

    def test_validate_dns_name_rejects_invalid_characters(self):
        invalid_names = [f"ab{char}cd" for char in ["(", ")", ":", ";"]] + ["ab$c"]
        for name in invalid_names:
            with self.subTest(name=name):
                self.assert_dns_name_validation_error(name, DNS_NAME_FORMAT_ERROR_MESSAGE)

    def test_validate_dns_name_rejects_labels_over_63_characters(self):
        self.assert_dns_name_validation_error("a" * 64, DNS_NAME_LENGTH_ERROR_MESSAGE)

    def test_validate_dns_name_rejects_names_over_253_characters(self):
        self.assert_dns_name_validation_error("a" * 254, DNS_NAME_LENGTH_ERROR_MESSAGE)
