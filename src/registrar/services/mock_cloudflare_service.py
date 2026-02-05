import httpx
import json
import respx
import logging
from datetime import datetime, timezone
from faker import Faker

from registrar.services.cloudflare_service import CloudflareService
from registrar.services.utility.dns_helper import make_dns_account_name

logger = logging.getLogger(__name__)

fake = Faker()


class MockCloudflareService:
    _instance = None
    _mock_context = None
    fake_zone_id = fake.uuid4().replace("-", "")  # Remove the 4 -'s in UUID4 to meet id's 32 char limit
    new_account_name = f"account-{fake.domain_name()}"
    existing_account_id = "a1234"
    existing_domain_name = "exists.gov"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.is_active = False
        self.domain_name = fake.domain_name()
        self.new_account_name = make_dns_account_name(self.domain_name)
        self.new_account_id = self._mock_create_cf_id()

    def start(self):
        """Start mocking external APIs"""
        if self.is_active:
            self.stop()  # to ensure clean start
        base_url = CloudflareService.base_url
        self._mock_context = respx.mock(base_url=base_url, assert_all_called=False, assert_all_mocked=False)
        self._mock_context.start()

        # Register all mock routes
        self._register_account_mocks()
        self._register_zone_mocks()

        self.is_active = True
        logger.debug("👌 Mock API Service: STARTED")

    def stop(self):
        """Stop mocking"""
        if self._mock_context and self.is_active:
            self._mock_context.stop()
            self.is_active = False
            logger.debug("🛑 Mock API Service: STOPPED")

    def _register_account_mocks(self):
        tenant_id = CloudflareService.tenant_id
        self._mock_context.get(f"/tenants/{tenant_id}/accounts", params={"page": 1, "per_page": 50}).mock(
            side_effect=self._mock_get_page_accounts_response
        )
        self._mock_context.post("/accounts").mock(side_effect=self._mock_create_account_response)

    def _register_zone_mocks(self):
        self._mock_context.get("/zones", params=f"account.id={self.existing_account_id}").mock(
            side_effect=self._mock_get_account_zones_response
        )
        self._mock_context.get("/zones", params=f"account.id={self.new_account_id}").mock(
            side_effect=self._mock_get_account_zones_response
        )
        self._mock_context.post("/zones").mock(side_effect=self._mock_create_cf_zone_response)

        # Mock the api with any zone id
        self._mock_context.post(url__regex=r"/zones/[\w-]+/dns_records").mock(
            side_effect=self._mock_create_dns_record_response
        )

        # Mock the api with any record id
        self._mock_context.post(url__regex=r"/zones/[\w-]+/dns_records/[\w-]+").mock(
            side_effect=self._mock_update_dns_record_response
        )

    def _mock_get_page_accounts_response(self, request) -> httpx.Response:
        logger.debug("😎 Mocking accounts GET")
        # use exists.gov domain to simulate an account that already exists
        return httpx.Response(
            200,
            json={
                "errors": [],
                "messages": [],
                "success": True,
                "result": [
                    {
                        "account_tag": "234asdf",
                        "account_pubname": "Account for hello.gov",
                        "account_type": "standard",
                        "created_on": "2025-10-08T21:07:18.651092Z",
                        "settings": {
                            "enforce_two_factor": False,
                            "api_access_enabled": False,
                            "access_approval_expiry": None,
                            "use_account_custom_ns_by_default": False,
                        },
                    },
                    {
                        "account_tag": self._mock_create_cf_id(),
                        "account_pubname": "Fake account name",
                        "account_type": "enterprise",
                        "created_on": "2025-10-08T21:21:38.401706Z",
                        "settings": {
                            "enforce_two_factor": False,
                            "api_access_enabled": False,
                            "access_approval_expiry": None,
                            "use_account_custom_ns_by_default": False,
                        },
                    },
                    {
                        "account_tag": self.existing_account_id,
                        "account_pubname": "Account for exists.gov",
                        "account_type": "enterprise",
                        "created_on": "2025-10-08T21:21:38.401706Z",
                        "settings": {
                            "enforce_two_factor": False,
                            "api_access_enabled": False,
                            "access_approval_expiry": None,
                            "use_account_custom_ns_by_default": False,
                        },
                    },
                ],
                "result_info": {"count": 3, "page": 1, "per_page": 50, "total_count": 3},
            },
        )

    def _mock_get_account_zones_response(self, request) -> httpx.Response:
        logger.debug("😎 Mocking zones GET")
        zone_name = self.domain_name
        account_id = request.url.params.get("account.id")
        zone_exists = account_id == self.existing_account_id

        # test with domain "exists.gov" to skip zone creation
        if zone_exists:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": [
                        {  # This record referenced for existing account with existing zone
                            "id": "z54321",
                            "account": {"id": self.existing_account_id, "name": "Account for exists.gov"},
                            "created_on": "2014-01-01T05:20:00.12345Z",
                            "modified_on": "2014-01-01T05:20:00.12345Z",
                            "name": "exists.gov",
                            "name_servers": [
                                "rainbow.dns.gov",
                                "rainbow2.dns.gov",
                            ],
                            "vanity_name_servers": [],
                            "status": "pending",
                            "tenant": {"id": CloudflareService.tenant_id, "name": "Fake dotgov"},
                        }
                    ],
                    "result_info": {"count": 1, "page": 1, "per_page": 20, "total_count": 1, "total_pages": 1},
                },
            )

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "id": self._mock_create_cf_id(),
                        "account": {"id": account_id, "name": self.new_account_name},
                        "created_on": "2014-01-01T05:20:00.12345Z",
                        "modified_on": "2014-01-01T05:20:00.12345Z",
                        "name": zone_name,
                        "name_servers": [
                            "rainbow.dns.gov",
                            "rainbow2.dns.gov",
                        ],
                        "vanity_name_servers": [],
                        "status": "pending",
                        "tenant": {"id": CloudflareService.tenant_id, "name": "Fake dotgov"},
                    },
                    {
                        "id": self._mock_create_cf_id(),
                        "account": {"id": account_id, "name": self.new_account_name},
                        "created_on": "2014-01-01T05:20:00.12345Z",
                        "modified_on": "2014-01-01T05:20:00.12345Z",
                        "name": "some.gov",
                        "name_servers": [
                            "rainbow.dns.gov",
                            "rainbow2.dns.gov",
                        ],
                        "vanity_name_servers": [],
                        "status": "pending",
                        "tenant": {"id": CloudflareService.tenant_id, "name": "Yet another fake dotgov"},
                    },
                ],
                "result_info": {"count": 1, "page": 1, "per_page": 20, "total_count": 1, "total_pages": 1},
            },
        )

    def _mock_create_account_response(self, request) -> httpx.Response:
        logger.debug("😎 mocking account create")
        request_as_json = json.loads(request.content.decode("utf-8"))
        account_name = request_as_json["name"]

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": self.new_account_id,
                    "name": account_name,
                    "type": "standard",
                    "created_on": datetime.now(timezone.utc).isoformat(),  # format "2014-03-01T12:21:02.0000Z",
                },
            },
        )

    def _mock_create_cf_zone_response(self, request) -> httpx.Response:
        logger.debug("😎 Mocking cf zone create")
        request_as_json = json.loads(request.content.decode("utf-8"))
        zone_name = request_as_json["name"]
        account_id = request_as_json["account"]["id"]

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": self.fake_zone_id,
                    "account": {"id": account_id, "name": make_dns_account_name(zone_name)},
                    "created_on": datetime.now(timezone.utc).isoformat(),
                    "modified_on": datetime.now(timezone.utc).isoformat(),
                    "name": zone_name,
                    "name_servers": [
                        "rainbow.dns.gov",
                        "rainbow2.dns.gov",
                    ],
                    "vanity_name_servers": [],
                    "status": "pending",
                    "tenant": {"id": CloudflareService.tenant_id, "name": "Fake dotgov"},
                },
            },
        )

    def _mock_create_dns_record_response(self, request) -> httpx.Response:
        logger.debug("😃 mocking dns record creation")
        request_as_json = json.loads(request.content.decode("utf-8"))
        record_name = request_as_json["name"]
        content = request_as_json["content"]
        type = request_as_json["type"]
        ttl = request_as_json.get("ttl") or 1
        comment = request_as_json.get("comment") or ""

        # TODO: add a variation of the 400 error for when a submitted name does not meet validation requirements
        if record_name.startswith("error"):
            if record_name.startswith("error-400"):
                return httpx.Response(
                    400,
                    json={
                        "result": None,
                        "success": False,
                        "errors": [{"code": 9005, "message": "Bad request for dns record."}],
                        "messages": [],
                    },
                )
            if record_name.startswith("error-403"):
                return httpx.Response(
                    403, json={"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]}
                )
            return httpx.Response(500)

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": self._mock_create_cf_id(),
                    "name": record_name,
                    "type": type,
                    "content": content,
                    "proxiable": True,
                    "proxied": False,
                    "ttl": ttl,
                    "settings": {},
                    "meta": {},
                    "comment": comment,
                    "tags": [],
                    "created_on": datetime.now(timezone.utc).isoformat(),
                    "modified_on": datetime.now(timezone.utc).isoformat(),
                },
                "success": True,
                "errors": [],
                "messages": [],
            },
        )

    def _mock_update_dns_record_response(self, request) -> httpx.Response:
        # Mocks updating a DNS A record.
        # If we want to mock updating other DNS records, we may want to split
        # this out and write a method to return a DNS record response by type.
        logger.debug("🐟 mocking dns A record update")
        request_as_json = json.loads(request.content.decode("utf-8"))
        record_name = request_as_json["name"]
        content = request_as_json["content"]
        type = request_as_json["type"]
        ttl = request_as_json.get("ttl") or 1
        comment = request_as_json.get("comment") or ""
        # Get record id from request url to return back in response
        request_url = str(request.url)
        # Split string between "/dns_records/ and extract second partition
        record_id = request_url.split("/dns_records/")[1]

        # TODO: add a variation of the 400 error for when a submitted name does not meet validation requirements
        if record_name.startswith("error"):
            if record_name.startswith("error-400"):
                return httpx.Response(
                    400,
                    json={
                        "result": None,
                        "success": False,
                        "errors": [{"code": 9005, "message": "Bad request for dns record."}],
                        "messages": [],
                    },
                )
            if record_name.startswith("error-403"):
                return httpx.Response(
                    403, json={"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]}
                )
            return httpx.Response(500)

        # Update response so it fits with whatever record we're returning
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": record_id,
                    "name": record_name,
                    "type": type,
                    "content": content,
                    "proxiable": True,
                    "proxied": False,
                    "ttl": ttl,
                    "settings": {},
                    "meta": {},
                    "comment": comment,
                    "tags": [],
                    "created_on": datetime.now(timezone.utc).isoformat(),
                    "modified_on": datetime.now(timezone.utc).isoformat(),
                },
                "success": True,
                "errors": [],
                "messages": [],
            },
        )

    def _mock_create_cf_id(self):
        """Create a 32 character UUID by removing the 4 -'s in a UUID4."""
        return fake.uuid4().replace("-", "")
