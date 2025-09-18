from unittest.mock import patch
from django.test import SimpleTestCase

from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError


class TestCloudflareService(SimpleTestCase):
    """Test cases for the CloudflareService class"""

    def setUp(self):
        self.service = CloudflareService()

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_create_account_success(self, mock_make_request):
        """Test successful create_account call"""
        account_name = "test.gov test account"
        mock_make_request.return_value = {"success": True, "data": {"result": {"name": account_name, "id": "12345"}}}
        result = self.service.create_account(account_name)
        self.assertEqual(result["result"]["name"], account_name)

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_create_account_failure(self, mock_make_request):
        """Test create_account with API failure"""
        account_name = " "
        mock_make_request.return_value = {"success": False, "details": "Cannot be empty"}

        with self.assertRaises(APIError) as context:
            self.service.create_account(account_name)

        self.assertIn(f"Failed to create account for {account_name}: Cannot be empty", str(context.exception))

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_create_zone_success(self, mock_make_request):
        """Test successful create_zone call"""
        account_name = "test.gov test account"
        account_id = "12345"
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "result": {
                    "name": account_name,
                    "id": "12345",
                    "nameservers": ["hostess1.mostess.gov", "hostess2.mostess.gov"],
                }
            },
        }
        result = self.service.create_zone(account_name, account_id)
        self.assertEqual(result["result"]["name"], account_name)

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_create_zone_failure(self, mock_make_request):
        """Test create_zone with API failure"""
        account_name = "test.gov test account"
        account_id = "12345"
        mock_make_request.return_value = {
            "success": False,
            "message": "invalid",
            "errors": ["you failed"],
            "details": "A bit more info!",
        }

        with self.assertRaises(APIError) as context:
            self.service.create_zone(account_name, account_id)

        self.assertIn(
            f"Failed to create zone for account {account_id}: errors: ['you failed'] message: invalid details:"
            + " A bit more info!",
            str(context.exception),
        )

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_create_dns_record_success(self, mock_make_request):
        """Test successful create_dns_record call"""
        zone_id = "54321"
        record_data = {
            "content": "198.51.100.4",
            "name": "democracy.gov",
            "proxied": False,
            "type": "A",
            "comment": "Test domain name",
            "ttl": 3600,
        }
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "result": {
                    "content": "198.51.100.4",
                    "name": "democracy.gov",
                    "proxied": False,
                    "type": "A",
                    "comment": "Test domain name",
                    "ttl": 3600,
                }
            },
        }
        result = self.service.create_dns_record(zone_id, record_data)
        self.assertEqual(result["result"]["name"], "democracy.gov")
        self.assertEqual(result["result"]["content"], "198.51.100.4")
        self.assertEqual(
            result["result"],
            {
                "content": "198.51.100.4",
                "name": "democracy.gov",
                "proxied": False,
                "type": "A",
                "comment": "Test domain name",
                "ttl": 3600,
            },
        )

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_create_dns_record_failure(self, mock_make_request):
        """Test create_zone with API failure"""
        zone_id = "54321"
        record_data_missing_content = {
            "name": "democracy.gov",
            "proxied": False,
            "type": "A",
            "comment": "Test domain name",
            "ttl": 3600,
        }
        mock_make_request.return_value = {
            "success": False,
            "message": "missing content field",
            "details": "more detail",
        }

        with self.assertRaises(APIError) as context:
            self.service.create_dns_record(zone_id, record_data_missing_content)

        self.assertIn(
            f"Failed to create dns record for zone {zone_id}: message: missing content field details: more detail",
            str(context.exception),
        )

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_get_page_accounts_success(self, mock_make_request):
        """Test successful get_all_accounts call"""
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "result": [
                    {"id": 1, "name": "test acct 1"},
                    {"id": 2, "name": "test acct 2"},
                ]
            },
        }

        result = self.service.get_page_accounts(1, 10)

        self.assertEqual(
            result,
            {
                "result": [
                    {"id": 1, "name": "test acct 1"},
                    {"id": 2, "name": "test acct 2"},
                ]
            },
        )

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_get_page_accounts_failure(self, mock_make_request):
        """Test get_all_accounts with API failure"""
        mock_make_request.return_value = {
            "success": False,
            "message": "Something is wrong",
            "details": "More info here",
        }

        with self.assertRaises(APIError) as context:
            self.service.get_page_accounts(1, 10)

        self.assertIn("Failed to get accounts", str(context.exception))

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_get_account_zones_success(self, mock_make_request):
        """Test successful get_account_zones call"""
        account_id = "55555"

        mock_make_request.return_value = {
            "success": True,
            "data": {
                "result": [
                    {"id": 1, "name": "test zone 1", "status": "active"},
                    {"id": 2, "name": "test zone 2", "status": "active"},
                ]
            },
        }

        result = self.service.get_account_zones(account_id)

        self.assertEqual(
            result,
            {
                "result": [
                    {"id": 1, "name": "test zone 1", "status": "active"},
                    {"id": 2, "name": "test zone 2", "status": "active"},
                ]
            },
        )

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_get_account_zones_failure(self, mock_make_request):
        """Test get_account_zones with API failure"""

        account_id = "44444"
        mock_make_request.return_value = {"success": False, "message": "Something is wrong"}

        with self.assertRaises(APIError) as context:
            self.service.get_account_zones(account_id)

        self.assertIn("Failed to get zones", str(context.exception))

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_get_dns_record_success(self, mock_make_request):
        """Test get_dns_record with API success"""
        zone_id = "1234"
        record_id = "45454"
        mock_make_request.return_value = {
            "success": True,
            "data": {"result": {"id": 2, "name": "A", "content": "198.22.333.4", "ttl": 3600}},
        }

        result = self.service.get_dns_record(zone_id, record_id)

        self.assertEqual(result, {"result": {"id": 2, "name": "A", "content": "198.22.333.4", "ttl": 3600}})

    @patch("registrar.services.cloudflare_service.make_api_request")
    def test_get_dns_record_failure(self, mock_make_request):
        """Test get_dns_record with API failure"""
        zone_id = ""
        record_id = "45454"
        mock_make_request.return_value = {
            "success": False,
            "message": "whomp, whomp",
            "details": "That means disappointment",
        }

        with self.assertRaises(APIError) as context:
            self.service.get_dns_record(zone_id, record_id)

        self.assertIn(
            "Failed to get dns record: message: whomp, whomp, details: That means disappointment",
            str(context.exception),
        )
