import httpx
import os
from unittest import mock
from unittest.mock import Mock
from django.test import SimpleTestCase
from httpx import Client, HTTPStatusError, RequestError
from typing import Any

from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import (
    APIError,
    DnsTransportError,
    DnsHostingErrorCodes,
    DnsValidationError,
    DnsNotFoundError,
    DnsRateLimitError,
    DnsAuthError,
    DnsHostingError,
)


class TestCloudflareService(SimpleTestCase):
    """Test cases for the CloudflareService class"""

    failure_cases: list[dict[str, Any]] = [
        {
            "test_name": "400ValidationError",
            "status_code": 400,
            "error": {
                "exception": HTTPStatusError,
                "raised_error": DnsValidationError,
                "code": DnsHostingErrorCodes.VALIDATION_FAILED,
                "cf_error_code": 48,
                "cf_error_message": "Needs more love",
            },
            "cf_ray": "135",
        },
        {
            "test_name": "DnsNotFoundError",
            "status_code": 404,
            "error": {
                "exception": HTTPStatusError,
                "raised_error": DnsNotFoundError,
                "code": DnsHostingErrorCodes.NOT_FOUND,
                "cf_error_code": 411,
                "cf_error_message": "Needs more info",
            },
            "cf_ray": "579",
        },
        {
            "test_name": "401DnsAuthError",
            "status_code": 401,
            "error": {
                "exception": HTTPStatusError,
                "raised_error": DnsAuthError,
                "code": DnsHostingErrorCodes.AUTH_FAILED,
                "cf_error_code": 10000,
                "cf_error_message": "Auth error",
            },
            "cf_ray": "K9",
        },
        {
            "test_name": "403DnsAuthError",
            "status_code": 403,
            "error": {
                "exception": HTTPStatusError,
                "raised_error": DnsAuthError,
                "code": DnsHostingErrorCodes.AUTH_FAILED,
                "cf_error_code": 10000,
                "cf_error_message": "Auth error",
            },
            "cf_ray": "KRS1",
        },
        {
            "test_name": "DnsRateLimitError",
            "status_code": 429,
            "error": {
                "exception": HTTPStatusError,
                "raised_error": DnsRateLimitError,
                "code": DnsHostingErrorCodes.RATE_LIMIT_EXCEEDED,
                "cf_error_code": 666,
                "cf_error_message": "Unlucky",
            },
            "cf_ray": "R2D2",
        },
        {
            "test_name": "UnmappedError",
            "status_code": 418,
            "error": {
                "exception": HTTPStatusError,
                "raised_error": DnsHostingError,
                "code": DnsHostingErrorCodes.UNKNOWN,
                "cf_error_code": 7777,
                "cf_error_message": "I'm a little teapot short and stout, not a coffee pot!",
            },
            "cf_ray": "TEAPOT",
        },
        {
            "test_name": "UpstreamError",
            "status_code": 500,
            "error": {
                "exception": HTTPStatusError,
                "raised_error": DnsHostingError,
                "code": DnsHostingErrorCodes.UPSTREAM_ERROR,
            },
            "cf_ray": "3CPO",
        },
        {
            "test_name": "RequestError",
            "error": {
                "exception": RequestError,
                "message": "There was an error getting a response",
                "raised_error": DnsTransportError,
                "code": DnsHostingErrorCodes.UPSTREAM_TIMEOUT,
            },
        },
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
        mock_client.delete = Mock()

        # Set class variable 'headers' to avoid double mocking
        CloudflareService.headers = {
            "X-Auth-Email": "test@test.gov",
            "X-Auth-Key": "12345",
            "Content-Type": "application/json",
        }
        self.service = CloudflareService(client=mock_client)

    def _get_failure_cases(self, cases_to_exclude_by_status_code: list[int] = None):
        if cases_to_exclude_by_status_code:
            return [c for c in self.failure_cases if c.get("status_code") not in cases_to_exclude_by_status_code]

        return self.failure_cases

    def _setUpSuccessMockResponse(self, return_value=None, raise_value=None):
        mock_response = Mock()
        mock_response.json.return_value = return_value
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = raise_value
        return mock_response

    def _setUpFailureMockResponse(self, error, status_code=None):
        mock_api_response = Mock()
        mock_api_response.status_code = status_code
        mock_api_response.text = error.get("message", "error response")
        http_error = None
        if error["exception"] in (APIError, HTTPStatusError):
            match status_code:
                case 400:
                    mock_response = httpx.Response(
                        400,
                        headers={"cf-ray": "135"},
                        json={
                            "result": None,
                            "success": False,
                            "errors": [{"code": 48, "message": "Needs more love"}],
                            "messages": [],
                        },
                    )
                    http_error = HTTPStatusError(request="something", response=mock_response, message="other thing")
                case 404:
                    mock_response = httpx.Response(
                        404,
                        headers={"cf-ray": "579"},
                        json={
                            "result": None,
                            "success": False,
                            "errors": [{"code": 411, "message": "Needs more info"}],
                            "messages": [],
                        },
                    )
                    http_error = HTTPStatusError(request="something", response=mock_response, message="other thing")
                case 429:
                    mock_response = httpx.Response(
                        429,
                        headers={"cf-ray": "R2D2"},
                        json={
                            "result": None,
                            "success": False,
                            "errors": [{"code": 666, "message": "Unlucky"}],
                            "messages": [],
                        },
                    )
                    http_error = HTTPStatusError(request="something", response=mock_response, message="other thing")
                case 401:
                    mock_response = httpx.Response(
                        401,
                        headers={"cf-ray": "K9"},
                        json={
                            "result": None,
                            "success": False,
                            "errors": [{"code": 10000, "message": "Auth error"}],
                            "messages": [],
                        },
                    )
                    http_error = HTTPStatusError(request="something", response=mock_response, message="other thing")
                case 403:
                    mock_response = httpx.Response(
                        403,
                        headers={"cf-ray": "KRS1"},
                        json={
                            "result": None,
                            "success": False,
                            "errors": [{"code": 10000, "message": "Auth error"}],
                            "messages": [],
                        },
                    )
                    http_error = HTTPStatusError(request="something", response=mock_response, message="other thing")
                case 418:
                    mock_response = httpx.Response(
                        418,
                        headers={"cf-ray": "TEAPOT"},
                        json={
                            "result": None,
                            "success": False,
                            "errors": [
                                {"code": 7777, "message": "I'm a little teapot short and stout, not a coffee pot!"}
                            ],
                            "messages": [],
                        },
                    )
                    http_error = HTTPStatusError(request="something", response=mock_response, message="other thing")
                case 500:
                    mock_response = httpx.Response(
                        500,
                        headers={"cf-ray": "3CPO"},
                    )
                    http_error = HTTPStatusError(request="something", response=mock_response, message="other thing")

        if error["exception"] == RequestError:
            http_error = RequestError(request="something", message="last thing")
        mock_api_response.raise_for_status.side_effect = http_error
        return mock_api_response

    def _assert_shared_http_status_errors_details(self, exception: DnsHostingError, case):
        self.assertEqual(exception.context["cf_ray"], case["cf_ray"])
        self.assertEqual(exception.upstream_status, case["status_code"])
        self.assertEqual(exception.context["cf_error_code"], case["error"].get("cf_error_code"))
        self.assertEqual(exception.context["cf_error_message"], case["error"].get("cf_error_message"))

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
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))

                self.service.client.post.return_value = mock_response

                with self.assertRaises(error["raised_error"]) as context:
                    self.service.create_cf_account(account_name)

                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["account_name"], account_name)

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
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))

                self.service.client.post.return_value = mock_response

                with self.assertRaises(error["raised_error"]) as context:
                    self.service.create_cf_zone(zone_name, account_id)

                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["zone_name"], zone_name)
                    self.assertEqual(exc.context["x_account_id"], account_id)

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
        """Test create_dns_record with API failure"""
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
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))

                self.service.client.post.return_value = mock_response

                with self.assertRaises(error["raised_error"]) as context:
                    self.service.create_dns_record(zone_id, record_data_missing_content)

                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["x_zone_id"], zone_id)
                    self.assertEqual(exc.context["record_data"], record_data_missing_content)

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
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))

                self.service.client.patch.return_value = mock_response

                with self.assertRaises(error["raised_error"]) as context:
                    self.service.update_dns_record(zone_id, record_id, record_data_invalid_content)

                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["x_zone_id"], zone_id)
                    self.assertEqual(exc.context["x_record_id"], record_id)
                    self.assertEqual(exc.context["record_data"], record_data_invalid_content)

    def test_delete_dns_record_success(self):
        """Test successful delete_dns_record call."""
        zone_id = "54321"
        record_id = "6789"
        return_value = {
            "success": True,
            "result": {
                "id": record_id,
            },
            "errors": [],
            "messages": [],
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.delete.return_value = mock_response

        resp = self.service.delete_dns_record(zone_id, record_id)

        self.assertTrue(resp["success"])
        self.assertEqual(resp["result"]["id"], record_id)
        self.assertEqual(resp["errors"], [])

    def test_delete_dns_record_failure(self):
        """Test failed delete_dns_record call."""
        zone_id = "54321"
        record_id = "6789"

        failure_cases = self._get_failure_cases([400, 409])
        for case in failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))

                self.service.client.delete.return_value = mock_response

                with self.assertRaises(error["raised_error"]) as context:
                    self.service.delete_dns_record(zone_id, record_id)

                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["x_zone_id"], zone_id)
                    self.assertEqual(exc.context["x_record_id"], record_id)

    def test_get_account_by_name_success(self):
        account_name = "Account for pride.gov"
        return_value = {
            "errors": [],
            "messages": [],
            "success": True,
            "result": [
                {
                    "account_tag": "54345",
                    "account_pubname": account_name,
                    "account_type": "enterprise",
                    "created_on": "2026-06-09T18:25:46.427351Z",
                }
            ],
            "result_info": {"count": 1, "page": 1, "per_page": 1, "total_count": 1},
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.get.return_value = mock_response
        result = self.service.get_account_by_name(account_name)
        self.assertEqual(result, return_value["result"][0])

    def test_get_account_by_name_failure(self):
        account_name = "Account for pride.gov"

        failure_cases = self._get_failure_cases([400, 409])
        for case in failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))
                self.service.client.get.return_value = mock_response
                with self.assertRaises(error["raised_error"]) as context:
                    self.service.get_account_by_name(account_name)
                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)

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

        failure_cases = self._get_failure_cases([400, 409, 404])
        for case in failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))
                self.service.client.get.return_value = mock_response
                with self.assertRaises(error["raised_error"]) as context:
                    self.service.get_account_zones(account_id)
                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)

    def test_get_zone_by_id_success(self):
        zone_id = "87678"
        return_value = {
            "result": {
                "id": zone_id,
            }
        }

        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.get.return_value = mock_response

        result = self.service.get_zone_by_id(zone_id)

        self.assertEqual(result, return_value)

    def test_get_zone_by_id_failure(self):
        zone_id = "876543"

        failure_cases = self._get_failure_cases([400, 409])
        for case in failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))
                self.service.client.get.return_value = mock_response
                with self.assertRaises(error["raised_error"]) as context:
                    self.service.get_zone_by_id(zone_id)
                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["x_zone_id"], zone_id)

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

        failure_cases = self._get_failure_cases([400, 409])
        for case in failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))
                self.service.client.get.return_value = mock_response
                with self.assertRaises(error["raised_error"]) as context:
                    self.service.get_dns_record(zone_id, record_id)
                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["x_zone_id"], zone_id)
                    self.assertEqual(exc.context["x_record_id"], record_id)

    def test_update_account_dns_settings_success(self):
        """Test successful update_account_dns_settings call"""
        account_id = "12345"
        return_value = {
            "success": True,
            "result": {
                "zone_defaults": {
                    "zone_mode": "dns_only",
                    "nameservers": {"type": "custom.tenant"},
                }
            },
            "errors": [],
            "messages": [],
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.patch.return_value = mock_response

        resp = self.service.update_account_dns_settings(account_id)

        self.assertTrue(resp.success)
        self.assertEqual(resp.result["zone_defaults"]["zone_mode"], "dns_only")
        self.assertEqual(resp.result["zone_defaults"]["nameservers"]["type"], "custom.tenant")
        self.assertEqual(resp.errors, [])

    def test_update_account_dns_settings_failure(self):
        """Test update_account_dns_settings with API failure"""
        account_id = "12345"

        for case in self.failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))
                self.service.client.patch.return_value = mock_response

                with self.assertRaises(error["raised_error"]) as context:
                    self.service.update_account_dns_settings(account_id)

                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["x_account_id"], account_id)

    def test_update_zone_dns_settings_success(self):
        """Test successful update_zone_dns_settings call"""
        zone_id = "54321"
        return_value = {
            "success": True,
            "result": {
                "zone_mode": "dns_only",
                "nameservers": {"ns_set": 2, "type": "custom.tenant"},
            },
            "errors": [],
            "messages": [],
        }
        mock_response = self._setUpSuccessMockResponse(return_value)
        self.service.client.patch.return_value = mock_response

        resp = self.service.update_zone_dns_settings(zone_id)

        self.assertTrue(resp.success)
        self.assertEqual(resp.result["zone_mode"], "dns_only")
        self.assertEqual(resp.result["nameservers"]["ns_set"], 2)
        self.assertEqual(resp.result["nameservers"]["type"], "custom.tenant")
        self.assertEqual(resp.errors, [])

    def test_update_zone_dns_settings_failure(self):
        """Test update_zone_dns_settings when error results during call"""
        zone_id = "54321"

        for case in self.failure_cases:
            with self.subTest(msg=case["test_name"], **case):
                error = case["error"]
                mock_response = self._setUpFailureMockResponse(error, case.get("status_code"))
                self.service.client.patch.return_value = mock_response

                with self.assertRaises(error["raised_error"]) as context:
                    self.service.update_zone_dns_settings(zone_id)

                exc = context.exception
                self.assertEqual(exc.code, case["error"]["code"])

                if case["error"]["exception"] == HTTPStatusError:
                    self._assert_shared_http_status_errors_details(exc, case)
                    self.assertEqual(exc.context["x_zone_id"], zone_id)
