from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from registrar.validations import (
    DNS_NAME_CONSECUTIVE_DOTS_REQUIREMENT,
    DNS_NAME_FORMAT_REQUIREMENT,
    DNS_NAME_HYPHEN_REQUIREMENT,
    DNS_NAME_LEADING_TRAILING_DOT_REQUIREMENT,
    DNS_NAME_SPACES_REQUIREMENT,
    validate_dns_name,
    validate_dns_name_fqdn_length,
    get_error_message_from_requirement,
    get_fqdn_error_message,
    _validate_dns_hostname_content,
    TXT_RECORD_CONTENT_MAX_LENGTH_ERROR_MESSAGE,
    TXT_RECORD_CONTENT_QUOTES_ERROR_MESSAGE,
    validate_txt_content,
)
from registrar.utility.enums import DNSRecordTypes


class TestValidateDNSName(SimpleTestCase):
    def assert_dns_name_validation_error(self, name: str, expected_message: str) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_dns_name(name)

        self.assertEqual(ctx.exception.messages, [expected_message])

    def assert_all_raise(self, names: list[str], expected_message: str) -> None:
        for name in names:
            with self.subTest(name=name):
                self.assert_dns_name_validation_error(name, expected_message)

    def assert_all_valid(self, names: list[str]) -> None:
        for name in names:
            with self.subTest(name=name):
                validate_dns_name(name)

    def test_validate_dns_name_allows_empty_name(self):
        validate_dns_name("")

    def test_validate_dns_name_allows_apex_name(self):
        validate_dns_name("@")

    def test_validate_dns_name_accepts_valid_names(self):
        self.assert_all_valid(["www", "WWW", "my-domain", "sub.domain", "*", "*.service", "a*b", "sub.*"])

    def test_validate_dns_name_rejects_names_with_spaces(self):
        names_with_spaces = [
            "ab cd",  # space in middle
            " abc",  # leading space
            "abc ",  # trailing space
            "a b c",  # multiple spaces
            "sub.domain name",  # space in a label of a multi-label name
        ]
        expected_error = get_error_message_from_requirement(DNS_NAME_SPACES_REQUIREMENT, "name")
        self.assert_all_raise(names_with_spaces, expected_error)

    def test_validate_dns_name_rejects_hyphen_at_label_boundary(self):
        expected_error = get_error_message_from_requirement(DNS_NAME_HYPHEN_REQUIREMENT, "name")
        self.assert_all_raise(["-abc", "abc-", "my.-domain", "my-.domain"], expected_error)

    def test_validate_dns_name_rejects_consecutive_dots(self):
        expected_error = get_error_message_from_requirement(DNS_NAME_CONSECUTIVE_DOTS_REQUIREMENT, "name")
        self.assert_dns_name_validation_error("ab..cd", expected_error)

    def test_validate_dns_name_rejects_leading_or_trailing_dot(self):
        expected_error = get_error_message_from_requirement(DNS_NAME_LEADING_TRAILING_DOT_REQUIREMENT, "name")
        self.assert_all_raise([".abc", "abc."], expected_error)

    def test_validate_dns_name_rejects_invalid_characters(self):
        invalid_names = [f"ab{char}cd" for char in ["(", ")", ":", ";", "@"]]
        expected_error = get_error_message_from_requirement(DNS_NAME_FORMAT_REQUIREMENT, "name")
        self.assert_all_raise(invalid_names, expected_error)

    def test_validate_dns_name_accepts_characters_not_in_blacklist(self):
        """Characters not in the AC's disallowed list should pass — including ones
        our prior whitelist rejected (underscore is load-bearing for _dmarc etc.)."""
        self.assert_all_valid(["_dmarc", "ab_cd", "ab,cd", "ab$cd", "ab!cd"])

    def test_validate_dns_name_rejects_labels_over_63_characters(self):
        error_message = get_fqdn_error_message()
        self.assert_dns_name_validation_error("a" * 64, error_message)

    def test_validate_dns_name_rejects_names_over_253_characters(self):
        error_message = get_fqdn_error_message()
        self.assert_dns_name_validation_error("a" * 254, error_message)


class TestValidateDNSNameFQDNLength(SimpleTestCase):
    ZONE = "example.gov"

    def assert_error(self, name: str, zone: str | None) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_dns_name_fqdn_length(name, zone)
        error_message = get_fqdn_error_message()
        self.assertEqual(ctx.exception.messages, [error_message])

    def test_no_error_when_zone_missing(self):
        validate_dns_name_fqdn_length("a" * 300, None)

    def test_no_error_when_name_empty(self):
        validate_dns_name_fqdn_length("", self.ZONE)

    def test_apex_fits_within_limit(self):
        validate_dns_name_fqdn_length("@", self.ZONE)

    def test_already_fully_qualified_name_is_not_double_appended(self):
        name = ("a" * 63) + "." + self.ZONE
        validate_dns_name_fqdn_length(name, self.ZONE)

    def test_relative_name_becomes_too_long_after_append(self):
        # 245 + "." + "example.gov" (11) = 257 chars → too long
        self.assert_error("a" * 245, self.ZONE)

    def test_relative_name_fits_after_append(self):
        # 240 + "." + "example.gov" = 252 chars → ok
        validate_dns_name_fqdn_length("a" * 240, self.ZONE)


class TestValidateDNSHostnameContent(SimpleTestCase):
    """
    Test validations specific to DNS hostname.
    Since hostname uses the same validators as record name when relevant, we only test
    hostname specific validations.
    """

    def test_validate_hostname_label_structure(self):
        invalid_label_hostnames = [
            ".ab",  # hostname cannot start with period
            "ab.1234",  # last label is a digit
            "a..b",  # no consecutive periods
        ]
        valid_label_hostnames = [
            "ab.",  # hostname can have trailing period
            "ab123",  # hostname can include numbers in label if alongisde non-numerical chars
            "ab.123a",  # hostname can end with label including numbers if alongside non-numerical chars
        ]

        for case in invalid_label_hostnames:
            with self.subTest(name=case):
                with self.assertRaises(ValidationError):
                    _validate_dns_hostname_content(case, DNSRecordTypes.MX)

        for case in valid_label_hostnames:
            with self.subTest(name=case):
                _validate_dns_hostname_content(case, DNSRecordTypes.MX)


class TestValidateDNSContent(SimpleTestCase):
    def assert_all_raise(self, contents: list[str], expected_message: str) -> None:
        for content in contents:
            with self.subTest(name=content):
                with self.assertRaises(ValidationError) as ctx:
                    validate_txt_content(content)

                self.assertEqual(ctx.exception.messages, [expected_message])

    def test_validate_txt_content(self):
        content_with_invalid_quoting = [
            '"starts with double quote',
            'ends with double quote"',
            '"is surrounded by double quotes"',
        ]
        self.assert_all_raise(content_with_invalid_quoting, TXT_RECORD_CONTENT_QUOTES_ERROR_MESSAGE)

        valid_content = ['Internal "quotes" are ok', "Single 'quotes' are ok", 'Stray "quote is ok']

        for content in valid_content:
            with self.subTest(name=content):
                validate_txt_content(content)

    def _test_validate_txt_content_max_length(self):

        max_length = 4080
        content_longer_than_max = "a" * max_length + "bc"

        with self.assertRaises(ValidationError) as ctx:
            validate_txt_content(content_longer_than_max)

        self.assertEqual(ctx.exception.messages, TXT_RECORD_CONTENT_MAX_LENGTH_ERROR_MESSAGE)
