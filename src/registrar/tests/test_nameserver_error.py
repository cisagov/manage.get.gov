from django.test import TestCase

from registrar.utility.errors import (
    NameserverError,
    NameserverErrorCodes as nsErrorCodes,
)


class TestNameserverError(TestCase):
    def test_with_no_ip(self):
        """Test NameserverError when no ip address is passed"""
        nameserver = "nameserver val"
        expected = "Using your domain for a name server requires an IP address."

        nsException = NameserverError(code=nsErrorCodes.MISSING_IP, nameserver=nameserver)
        self.assertEqual(nsException.message, expected)
        self.assertEqual(nsException.code, nsErrorCodes.MISSING_IP)

    def test_with_only_code(self):
        """Test NameserverError when no ip address
        and no nameserver is passed"""
        nameserver = "nameserver val"
        expected = "You can't have more than 13 nameservers."

        nsException = NameserverError(code=nsErrorCodes.TOO_MANY_HOSTS, nameserver=nameserver)
        self.assertEqual(nsException.message, expected)
        self.assertEqual(nsException.code, nsErrorCodes.TOO_MANY_HOSTS)

    def test_with_ip_nameserver(self):
        """Test NameserverError when ip and nameserver are passed"""
        ip = "ip val"
        nameserver = "nameserver val"

        expected = f"{nameserver}: Enter an IP address in the required format."
        nsException = NameserverError(code=nsErrorCodes.INVALID_IP, nameserver=nameserver, ip=ip)
        self.assertEqual(nsException.message, expected)
        self.assertEqual(nsException.code, nsErrorCodes.INVALID_IP)
