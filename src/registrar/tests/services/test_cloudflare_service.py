from unittest.mock import patch, Mock
from django.test import SimpleTestCase
from httpx import HTTPStatusError

from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError


class TestCloudflareService(SimpleTestCase):
    """Test cases for the CloudflareService class"""

    def setUp(self):
        self.service = CloudflareService()

    @patch("registrar.services.cloudflare_service.Client.post")
    def test_create_account_success(self, mock_post):
        """Test successful create_account call"""
        account_name = "test.gov test account"
        mock_response = Mock()
        mock_response.json.return_value = {"result": {"name": account_name, "id": "12345"}}
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
       
        resp = self.service.create_account(account_name)
        self.assertEqual(resp["result"]["name"], account_name)

    @patch("registrar.services.cloudflare_service.Client.post")
    def test_create_account_failure(self, mock_post):
        """Test create_account with API failure"""
        account_name = " "
        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(request="something", response="400 Server Error", message="Cannot be empty")
        http_error.response = mock_response
        mock_post.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.create_account(account_name)

        self.assertIn(f"Cannot be empty", str(context.exception))

    @patch("registrar.services.cloudflare_service.Client.post")
    def test_create_zone_success(self, mock_post):
        """Test successful create_zone call"""
        zone_name = "test.gov"
        account_id = "12345"
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {
                "name": zone_name,
                "id": "12345",
                "nameservers": ["hostess1.mostess.gov", "hostess2.mostess.gov"],
            }
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        resp = self.service.create_zone(zone_name, account_id)
        self.assertEqual(resp["result"]["name"], zone_name)

    @patch("registrar.services.cloudflare_service.Client.post")
    def test_create_zone_failure(self, mock_post):
        """Test create_zone with API failure"""
        zone_name = "test.gov"
        account_id = "12345"
        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(request="something", response="400 Server Error", message="Error creating zone")
        http_error.response = mock_response
        mock_post.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.create_zone(zone_name, account_id)
        self.assertIn(
            "Error creating zone",
            str(context.exception),
        )

    @patch("registrar.services.cloudflare_service.Client.post")
    def test_create_dns_record_success(self, mock_post):
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
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
                "result": {
                    "content": "198.51.100.4",
                    "name": "democracy.gov",
                    "proxied": False,
                    "type": "A",
                    "comment": "Test domain name",
                    "ttl": 3600,
                }
        }

        mock_post.return_value = mock_response
        resp = self.service.create_dns_record(zone_id, record_data)
        self.assertEqual(resp["result"]["name"], "democracy.gov")
        self.assertEqual(resp["result"]["content"], "198.51.100.4")
        self.assertEqual(
            resp["result"],
            {
                "content": "198.51.100.4",
                "name": "democracy.gov",
                "proxied": False,
                "type": "A",
                "comment": "Test domain name",
                "ttl": 3600,
            },
        )

    @patch("registrar.services.cloudflare_service.Client.post")
    def test_create_dns_record_failure(self, mock_post):
        """Test create_zone with API failure"""
        zone_id = "54321"
        record_data_missing_content = {
            "name": "democracy.gov",
            "proxied": False,
            "type": "A",
            "comment": "Test domain name",
            "ttl": 3600,
        }
        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(request="something", response="400 Server Error", message="Error creating DNS record")
        http_error.response = mock_response
        mock_post.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.create_dns_record(zone_id, record_data_missing_content)

        self.assertIn(
            f"Error creating DNS record",
            str(context.exception),
        )

    @patch("registrar.services.cloudflare_service.Client.get")
    def test_get_page_accounts_success(self, mock_get):
        """Test successful get_all_accounts call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": [
                {"id": 1, "name": "test acct 1"},
                {"id": 2, "name": "test acct 2"},
            ]
        }
        mock_get.return_value = mock_response

        resp = self.service.get_page_accounts(1, 10)
        self.assertEqual(
            resp,
            {
                "result": [
                    {"id": 1, "name": "test acct 1"},
                    {"id": 2, "name": "test acct 2"},
                ]
            },
        )

    @patch("registrar.services.cloudflare_service.Client.get")
    def test_get_page_accounts_failure(self, mock_get):
        """Test get_all_accounts with API failure"""

        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(request="something", response="400 Server Error", message="Error fetching accounts")
        http_error.response = mock_response
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.get_page_accounts(1, 10)

        self.assertIn("Error fetching accounts", str(context.exception))

    @patch("registrar.services.cloudflare_service.Client.get")
    def test_get_account_zones_success(self, mock_get):
        """Test successful get_account_zones call"""
        account_id = "55555"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": [
                {"id": 1, "name": "test zone 1", "status": "active"},
                {"id": 2, "name": "test zone 2", "status": "active"},
            ]
        }
        mock_get.return_value = mock_response

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

    @patch("registrar.services.cloudflare_service.Client.get")
    def test_get_account_zones_failure(self, mock_get):
        """Test get_account_zones with API failure"""

        account_id = "44444"
        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(request="something", response="400 Server Error", message="Error fetching zone")
        http_error.response = mock_response
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.get_account_zones(account_id)

        self.assertIn("Error fetching zone", str(context.exception))

    @patch("registrar.services.cloudflare_service.Client.get")
    def test_get_dns_record_success(self, mock_get):
        """Test get_dns_record with API success"""
        zone_id = "1234"
        record_id = "45454"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {"id": 2, "name": "A", "content": "198.22.333.4", "ttl": 3600},
        }
        mock_get.return_value = mock_response

        resp = self.service.get_dns_record(zone_id, record_id)

        self.assertEqual(resp, {"result": {"id": 2, "name": "A", "content": "198.22.333.4", "ttl": 3600}})

    @patch("registrar.services.cloudflare_service.Client.get")
    def test_get_dns_record_failure(self, mock_get):
        """Test get_dns_record with API failure"""
        zone_id = "1"
        record_id = "45454"

        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(request="something", response="400 Server Error", message="Error fetching dns record")
        http_error.response = mock_response
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.get_dns_record(zone_id, record_id)

        self.assertIn(
            "Error fetching dns record",
            str(context.exception),
        )
