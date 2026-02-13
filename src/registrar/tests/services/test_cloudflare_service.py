import os
from unittest import mock
from unittest.mock import Mock
from django.test import SimpleTestCase
from httpx import Client, HTTPStatusError, RequestError

from registrar.services.cloudflare_service import CloudflareService


class TestCloudflareService(SimpleTestCase):
    """Test cases for the CloudflareService class"""

    failure_cases = [
        {
            "test_name": "HTTPStatusError",
            "error": {"exception": HTTPStatusError, "response": "400 Server Error", "message": "Error doing the thing"},
        },
        {"test_name": "RequestError", "error": {"exception": RequestError, "message": "Unknown error"}},
    ]

    @classmethod
    def setUpClass(cls):
        patcher = mock.patch.dict(os.environ, {"DNS_SERVICE_EMAIL": "test@test.gov", "DNS_TENANT_KEY": "12345"})
        patcher.start()
        cls.addClassCleanup(patcher.stop)

        super().setUpClass()

    def setUp(self):
        mock_client = Client()
        mock_client.post = Mock()
        mock_client.get = Mock()
        mock_client.patch = Mock()

        # Set class variable 'headers' to avoid double mocking
        CloudflareService.headers = {
            "X-Auth-Email": "test@test.gov",
            "X-Auth-Key": "12345",
            "Content-Type": "application/json",
        }
        self.service = CloudflareService(client=mock_client)

    def _setUpSuccessMockResponse(self, return_value=None, raise_value=None):
        mock_response = Mock()
        mock_response.json.return_value = return_value
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = raise_value
        return mock_response

    def _setUpFailureMockResponse(self, error, status_code=400):
        mock_response = Mock()
        mock_response.status_code = status_code
        http_error = None
        if error["exception"] == HTTPStatusError:
            http_error = HTTPStatusError(request="something", response=error["response"], message=error["message"])
        if error["exception"] == RequestError:
            http_error = RequestError(request="something", message=error["message"])
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        return mock_response

    def test_create_cf_account_success(self):
        """Test successful create_cf_account call"""
        account_name = "test.gov test account"
        mock_response = self._setUpSuccessMockResponse(return_value={"result": {"name": account_name, "id": "12345"}})
        self.service.client.post.return_value = mock_response

        resp = self.service.create_cf_account(account_name)
        self.assertEqual(resp["result"]["name"], account_name)

    def test_create_cf_account_failure(self):
        """Test create_cf_account with API failure"""
        account_name = "My get.gov"
        for case in self.failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                account_name = case["test_name"]
                error = case["error"]

                mock_response = self._setUpFailureMockResponse(error)
                self.service.client.post.return_value = mock_response

                with self.assertRaises(case["error"]["exception"]) as context:
                    self.service.create_cf_account(account_name)

                self.assertIn(case["error"]["message"], str(context.exception))

    def test_create_cf_zone_success(self):
        """Test successful create_cf_zone call"""
        zone_name = "test.gov"
        account_id = "12345"
        return_value = {
            "result": {
                "name": zone_name,
                "id": "12345",
                "nameservers": ["hostess1.mostess.gov", "hostess2.mostess.gov"],
            }
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.post.return_value = mock_response
        resp = self.service.create_cf_zone(zone_name, account_id)
        self.assertEqual(resp["result"]["name"], zone_name)

    def test_create_cf_zone_failure(self):
        """Test create_cf_zone with API failure"""
        zone_name = "test.gov"
        account_id = "12345"

        for case in self.failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error)

                self.service.client.post.return_value = mock_response

                with self.assertRaises(error["exception"]) as context:
                    self.service.create_cf_zone(zone_name, account_id)
                self.assertIn(
                    error["message"],
                    str(context.exception),
                )

    def test_create_dns_record_success(self):
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
        return_value = {
            "result": {
                "content": "198.51.100.4",
                "name": "democracy.gov",
                "proxied": False,
                "type": "A",
                "comment": "Test domain name",
                "ttl": 3600,
            }
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.post.return_value = mock_response
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

    def test_create_dns_record_failure(self):
        """Test create_cf_zone with API failure"""
        zone_id = "54321"
        record_data_missing_content = {
            "name": "democracy.gov",
            "proxied": False,
            "type": "A",
            "comment": "Test domain name",
            "ttl": 3600,
        }

        for case in self.failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error)

                self.service.client.post.return_value = mock_response

                with self.assertRaises(error["exception"]) as context:
                    self.service.create_dns_record(zone_id, record_data_missing_content)
                self.assertIn(
                    error["message"],
                    str(context.exception),
                )

    def test_update_dns_record_success(self):
        """Test successful update_dns_record call"""
        zone_id = "54321"
        record_id = "6789"
        created_record_data = {
            "content": "198.51.100.4",
            "name": "democracy.gov",
            "proxied": False,
            "type": "A",
            "comment": "Test domain name",
            "ttl": 3600,
        }

        created_return_value = {
            "result": {
                "content": "198.51.100.4",
                "name": "democracy.gov",
                "proxied": False,
                "type": "A",
                "comment": "Test domain name",
                "ttl": 3600,
            }
        }
        updated_record_data = {
            "content": "198.62.211.5",
            "name": "updated-record.gov",
            "proxied": False,
            "type": "A",
            "comment": "Test record update",
            "ttl": 3600,
        }
        updated_return_value = {
            "result": {
                "content": "198.62.211.5",
                "name": "updated-record.gov",
                "proxied": False,
                "type": "A",
                "comment": "Test record update",
                "ttl": 1800,
            }
        }
        mock_create_response = self._setUpSuccessMockResponse(created_return_value)
        self.service.client.post.return_value = mock_create_response
        self.service.create_dns_record(zone_id, created_record_data)

        mock_update_response = self._setUpSuccessMockResponse(updated_return_value)
        self.service.client.patch.return_value = mock_update_response
        resp = self.service.update_dns_record(zone_id, record_id, updated_record_data)
        self.assertEqual(resp["result"]["name"], "updated-record.gov")
        self.assertEqual(resp["result"]["content"], "198.62.211.5")
        self.assertEqual(resp["result"]["comment"], "Test record update")
        self.assertEqual(resp["result"]["ttl"], 1800)
        self.assertEqual(
            resp["result"],
            {
                "content": "198.62.211.5",
                "name": "updated-record.gov",
                "proxied": False,
                "type": "A",
                "comment": "Test record update",
                "ttl": 1800,
            },
        )

    def test_update_dns_record_failure(self):
        """Test update_cf_zone with API failure"""
        zone_id = "54321"
        record_id = "6789"
        record_data_invalid_content = {
            "name": "democracy.gov",
            "content": "not an IP address",
            "proxied": False,
            "type": "A",
            "comment": "Test domain name",
            "ttl": 3600,
        }

        for case in self.failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error)

                self.service.client.patch.return_value = mock_response

                with self.assertRaises(error["exception"]) as context:
                    self.service.update_dns_record(zone_id, record_id, record_data_invalid_content)
                self.assertIn(
                    error["message"],
                    str(context.exception),
                )

    def test_get_page_accounts_success(self):
        """Test successful get_page_accounts call"""
        return_value = {
            "result": [
                {"id": 1, "name": "test acct 1"},
                {"id": 2, "name": "test acct 2"},
            ]
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.get.return_value = mock_response

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

    def test_get_page_accounts_failure(self):
        """Test get_all_accounts with API failure"""

        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(
            request="something", response="400 Server Error", message="Error fetching accounts"
        )
        http_error.response = mock_response
        self.service.client.get.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.get_page_accounts(1, 10)

        self.assertIn("Error fetching accounts", str(context.exception))

    def test_get_account_zones_success(self):
        """Test successful get_account_zones call"""
        account_id = "55555"
        return_value = {
            "result": [
                {"id": 1, "name": "test zone 1", "status": "active"},
                {"id": 2, "name": "test zone 2", "status": "active"},
            ]
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.get.return_value = mock_response

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

    def test_get_account_zones_failure(self):
        """Test get_account_zones with API failure"""

        account_id = "44444"
        mock_response = Mock()
        mock_response.status_code = 400
        http_error = HTTPStatusError(request="something", response="400 Server Error", message="Error fetching zone")
        http_error.response = mock_response
        self.service.client.get.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with self.assertRaises(HTTPStatusError) as context:
            self.service.get_account_zones(account_id)

        self.assertIn("Error fetching zone", str(context.exception))

    def test_get_dns_record_success(self):
        """Test get_dns_record with API success"""
        zone_id = "1234"
        record_id = "45454"
        return_value = {
            "result": {"id": 2, "name": "A", "content": "198.22.333.4", "ttl": 3600},
        }
        mock_response = self._setUpSuccessMockResponse(return_value=return_value)
        self.service.client.get.return_value = mock_response

        resp = self.service.get_dns_record(zone_id, record_id)

        self.assertEqual(resp, return_value)

    def test_get_dns_record_failure(self):
        """Test get_dns_record with API failure"""
        zone_id = "1"
        record_id = "45454"

        for case in self.failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error)
                self.service.client.get.return_value = mock_response

                with self.assertRaises(error["exception"]) as context:
                    self.service.get_dns_record(zone_id, record_id)

                self.assertIn(
                    error["message"],
                    str(context.exception),
                )
