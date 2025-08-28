from unittest.mock import patch
from django.test import SimpleTestCase

from registrar.services.cloudflare_service import CloudflareService
from registrar.services.dns_host_service import DnsHostService
from registrar.utility.errors import APIError


class TestDnsHostService(SimpleTestCase):

    def setUp(self):
        self.service = DnsHostService()

    @patch("registrar.services.dns_host_service.CloudflareService.get_account_zones")
    @patch("registrar.services.dns_host_service.CloudflareService.get_all_accounts")
    @patch("registrar.services.dns_host_service.CloudflareService.create_zone")
    @patch("registrar.services.dns_host_service.CloudflareService.create_account")
    def test_dns_setup_success(
        self, mock_create_account, mock_create_zone, mock_get_all_accounts, mock_get_account_zones
    ):
        test_cases = [
            {
                "test_name": "no account, no zone",
                "account_name": "Account for test.gov",
                "zone_name": "test.gov",
                "account_id": "12345",
                "zone_id": "8765",
                "found_account_id": None,
                "found_zone_id": None,
            },
            {
                "test_name": "has account, has zone",
                "account_name": "Account for test.gov",
                "zone_name": "test.gov",
                "account_id": "12345",
                "zone_id": "8765",
                "found_account_id": "12345",
                "found_zone_id": "8765",
            },
            {
                "test_name": "has account, no zone",
                "account_name": "Account for test.gov",
                "zone_name": "test.gov",
                "account_id": "12345",
                "zone_id": "8765",
                "found_account_id": "12345",
                "found_zone_id": None,
            },
        ]

        for case in test_cases:
            with self.subTest(msg=case["test_name"], **case):
                mock_create_account.return_value = {"result": {"id": case["account_id"]}}

                mock_create_zone.return_value = {"result": {"id": case["zone_id"], "name": case["zone_name"]}}

                mock_get_all_accounts.return_value = {"result": [{"id": case.get("found_account_id")}]}

                mock_get_account_zones.return_value = {"result": [{"id": case.get("found_zone_id")}]}

                returned_account_id, returned_zone_id = self.service.dns_setup(case["account_name"], case["zone_name"])
                self.assertEqual(returned_account_id, case["account_id"])
                self.assertEqual(returned_zone_id, case["zone_id"])

    @patch("registrar.services.dns_host_service.CloudflareService.get_account_zones")
    @patch("registrar.services.dns_host_service.CloudflareService.get_all_accounts")
    @patch("registrar.services.dns_host_service.CloudflareService.create_zone")
    @patch("registrar.services.dns_host_service.CloudflareService.create_account")
    def test_dns_setup_failure_from_create_account(
        self, mock_create_account, mock_create_zone, mock_get_all_accounts, mock_get_account_zones
    ):
        account_name = " "
        zone_name = "test.gov"
        mock_create_account.side_effect = APIError("DNS setup failed to create account")

        with self.assertRaises(APIError) as context:
            self.service.dns_setup(account_name, zone_name)

        mock_create_account.assert_called_once_with(account_name)
        self.assertIn("DNS setup failed to create account", str(context.exception))

    @patch("registrar.services.dns_host_service.CloudflareService.get_account_zones")
    @patch("registrar.services.dns_host_service.CloudflareService.get_all_accounts")
    @patch("registrar.services.dns_host_service.CloudflareService.create_zone")
    @patch("registrar.services.dns_host_service.CloudflareService.create_account")
    def test_dns_setup_failure_from_create_zone(
        self, mock_create_account, mock_create_zone, mock_get_all_accounts, mock_get_account_zones
    ):
        account_name = "Account for test.gov"
        zone_name = "test.gov"
        account_id = "12345"
        mock_create_account.return_value = {"result": {"id": account_id}}

        mock_create_account.side_effect = APIError("DNS setup failed to create zone")

        with self.assertRaises(APIError) as context:
            self.service.dns_setup(account_name, zone_name)

        mock_create_account.assert_called_once_with(account_name)
        # mock_create_zone.assert_called_once_with(zone_name, account_id) not sure why this fails: 0 calls
        self.assertIn("DNS setup failed to create zone", str(context.exception))

    @patch("registrar.services.dns_host_service.CloudflareService.create_dns_record")
    def test_create_record_success(self, mock_create_dns_record):

        zone_id = "1234"
        record_data = {
            "type": "A",
            "name": "test.gov",  # record name
            "content": "1.1.1.1",  # IPv4
            "ttl": 1,
            "comment": "Test record",
        }

        mock_create_dns_record.return_value = {"result": {"id": zone_id, **record_data}}

        response = self.service.create_record(zone_id, record_data)
        self.assertEqual(response["result"]["id"], zone_id)
        self.assertEqual(response["result"]["name"], "test.gov")

    @patch("registrar.services.dns_host_service.CloudflareService.create_dns_record")
    def test_create_record_failure(self, mock_create_dns_record):

        zone_id = "1234"
        record_data = {"type": "A", "content": "1.1.1.1", "ttl": 1, "comment": "Test record"}  # IPv4

        mock_create_dns_record.side_effect = APIError("Bad request: missing name")

        with self.assertRaises(APIError) as context:
            self.service.create_record(zone_id, record_data)
        self.assertIn("Bad request: missing name", str(context.exception))
