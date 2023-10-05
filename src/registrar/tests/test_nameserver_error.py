from django.test import TestCase

from registrar.models.utility.nameserver_error import (
    NameserverError,
    NameserverErrorCodes as nsErrorCodes,
)


class TestNameserverError(TestCase):
    def test_with_no_ip(self):
        """Test NameserverError when no ip address is passed"""
        nameserver = "nameserver val"
        expected = (
            f"Nameserver {nameserver} needs to have an "
            "IP address because it is a subdomain"
        )

        nsException = NameserverError(
            code=nsErrorCodes.MISSING_IP, nameserver=nameserver
        )
        self.assertEqual(nsException.message, expected)
        self.assertEqual(nsException.code, nsErrorCodes.MISSING_IP)

    def test_with_only_code(self):
        """Test NameserverError when no ip address
        and no nameserver is passed"""
        nameserver = "nameserver val"
        expected = "Too many hosts provided, you may not have more than 13 nameservers."

        nsException = NameserverError(
            code=nsErrorCodes.TOO_MANY_HOSTS, nameserver=nameserver
        )
        self.assertEqual(nsException.message, expected)
        self.assertEqual(nsException.code, nsErrorCodes.TOO_MANY_HOSTS)

    def test_with_ip_nameserver(self):
        """Test NameserverError when ip and nameserver are passed"""
        ip = "ip val"
        nameserver = "nameserver val"

        expected = f"Nameserver {nameserver} has an invalid IP address: {ip}"
        nsException = NameserverError(
            code=nsErrorCodes.INVALID_IP, nameserver=nameserver, ip=ip
        )
        self.assertEqual(nsException.message, expected)
        self.assertEqual(nsException.code, nsErrorCodes.INVALID_IP)
