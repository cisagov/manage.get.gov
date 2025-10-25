import httpx
import json
import respx
import logging
from datetime import datetime, timezone
from faker import Faker
from random import randint

from registrar.services.cloudflare_service import CloudflareService

logger = logging.getLogger(__name__)

fake = Faker()


class MockCloudflareService:
    _instance = None
    _mock_context = None
    fake_record_id = fake.uuid4()
    new_account_name = f"account-{fake.domain_name}"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.is_active = False

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
        self._mock_context.post(f"/accounts").mock(side_effect=self._mock_create_account_response)

    def _register_zone_mocks(self):
        self._mock_context.get(f"/zones", params=f"account.id=1234").mock(
            side_effect=self._mock_get_account_zones_response
        )
        self._mock_context.post(f"/zones").mock(side_effect=self._mock_create_zone_response)
        self._mock_context.post(f"/zones/{self.fake_record_id}/dns_records").mock(
            side_effect=self._mock_create_dns_record_response
        )

    def _mock_get_page_accounts_response(self, request):
        logger.debug("😎 Mocking accounts get")

        return httpx.Response(
            200,
            json={
                "errors": [],
                "messages": [],
                "success": True,
                "result": [
                    {
                        "account_tag": "234asdf",
                        "account_pubname": "hello.gov",
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
                        "account_tag": fake.uuid4(),
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
                        "account_tag": "1234",
                        "account_pubname": "account-exists.gov",  # use exists.gov domain to simulate an account that already exists
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

    def _mock_get_account_zones_response(self, request):
        request_as_json = json.loads(request.content.decode("utf-8"))
        zone_name = request_as_json["name"]
        account_id = request_as_json["account"]["id"]

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "id": fake.uuid4(),
                        "account": {"id": account_id, "name": self.new_account_name},
                        "created_on": "2014-01-01T05:20:00.12345Z",
                        "modified_on": "2014-01-01T05:20:00.12345Z",
                        "name": zone_name,
                        "name_servers": [
                            "rainbow.dns.gov",
                            "rainbow2.dns.gov",
                        ],
                        "status": "pending",
                        "tenant": {"id": CloudflareService.tenant_id, "name": "Fake dotgov"},
                    }
                ],
                "result_info": {"count": 1, "page": 1, "per_page": 20, "total_count": 1, "total_pages": 1},
            },
        )

    def _mock_create_zone_response(self, request):
        logger.debug("😎 Mocking zone create")
        request_as_json = json.loads(request.content.decode("utf-8"))
        zone_name = request_as_json["name"]
        account_id = request_as_json["account"]["id"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": self.fake_record_id,
                    "account": {"id": account_id, "name": "account-found-my.gov"},
                    "created_on": "2014-01-01T05:20:00.12345Z",
                    "modified_on": "2014-01-01T05:20:00.12345Z",
                    "name": zone_name,
                    "name_servers": [
                        "rainbow.dns.gov",
                        "rainbow2.dns.gov",
                    ],
                    "status": "pending",
                    "tenant": {"id": CloudflareService.tenant_id, "name": "Fake dotgov"},
                },
            },
        )

    def _mock_create_account_response(self, request):
        logger.debug("😎 mocking account create")
        request_as_json = json.loads(request.content.decode("utf-8"))
        account_name = request_as_json["name"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "24681359",
                    "name": account_name,
                    "type": "standard",  # enterprise?
                    "created_on": datetime.now(timezone.utc).isoformat(),  # format "2014-03-01T12:21:02.0000Z",
                },
            },
        )

    def _mock_create_dns_record_response(self, request):
        logger.debug("😃 mocking dns record creation")
        request_as_json = json.loads(request.content.decode("utf-8"))
        record_name = request_as_json["name"]
        content = request_as_json["content"]
        type = request_as_json["type"]
        ttl = request_as_json.get("ttl") or 1

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": fake.uuid4(),
                    "name": record_name,
                    "type": type,
                    "content": content,
                    "proxiable": True,
                    "proxied": False,
                    "ttl": ttl,
                    "settings": {},
                    "meta": {},
                    "comment": "Mocked A record created",
                    "tags": [],
                    "created_on": "2025-10-22T03:38:21.614099Z",
                    "modified_on": "2025-10-22T03:38:21.614099Z",
                },
                "success": True,
                "errors": [],
                "messages": [],
            },
        )
