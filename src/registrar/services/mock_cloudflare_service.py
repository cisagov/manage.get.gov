import httpx
import json
import respx
from datetime import datetime, timezone
from faker import Faker
from random import randint

from registrar.services.cloudflare_service import CloudflareService


fake = Faker()

class MockCloudflareService:
    _instance = None
    _mock_context = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
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


        self.is_active = True
        print("👌 Mock API Service: STARTED")

    def stop(self):
        """Stop mocking"""
        if self._mock_context and self.is_active:
            self._mock_context.stop()
            self.is_active = False
            print("🛑 Mock API Service: STOPPED")

    def _register_account_mocks(self):
        tenant_id = CloudflareService.tenant_id
        self._mock_context.get(f"/tenants/{tenant_id}/accounts", params={"page": 1, "per_page": 50}).mock(side_effect=self._mock_get_page_accounts_response)
        self._mock_context.get(f"/zones", params=f"account.id=1234").mock(side_effect=self._mock_get_account_zones_response)
        self._mock_context.post(f"/accounts").mock(side_effect=self._mock_create_account_response)
        self._mock_context.post(f"/zones").mock(side_effect=self._mock_create_zone_response)

    def _mock_get_page_accounts_response(self, request):
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
                            "use_account_custom_ns_by_default": False
                        },
                    },
                    {
                        "account_tag": "1234",
                        "account_pubname": "account-found-my.gov",
                        "account_type": "enterprise",
                        "created_on": "2025-10-08T21:21:38.401706Z",
                        "settings": {
                            "enforce_two_factor": False,
                            "api_access_enabled": False,
                            "access_approval_expiry": None,
                            "use_account_custom_ns_by_default": False
                        },
                    }
                ],
                "result_info": {
                    "count": 2,
                    "page": 1,
                    "per_page": 50,
                    "total_count": 2
                }
            }
        )

    def _mock_get_account_zones_response(self, request):
        request_as_json = json.loads(request.content.decode('utf-8'))
        zone_name = request_as_json["name"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "id": "789",
                        "account": {
                            "id": "1234",
                            "name": "account-found-my.gov"
                        },
                        "created_on": "2014-01-01T05:20:00.12345Z",
                        "modified_on": "2014-01-01T05:20:00.12345Z",
                        "name": zone_name,
                        "name_servers": [
                            "rainbow.dns.gov",
                            "rainbow2.dns.gov",
                        ],
                        "status": "pending",
                        "tenant": {
                            "id": CloudflareService.tenant_id,
                            "name": "Fake dotgov"
                        }
                    }
                ],
                "result_info": {
                    "count": 1,
                    "page": 1,
                    "per_page": 20,
                    "total_count": 1,
                    "total_pages": 1
                }
            }
        )

    def _mock_create_zone_response(self, request):
        request_as_json = json.loads(request.content.decode('utf-8'))
        zone_name = request_as_json["name"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "789",
                    "account": {
                        "id": "1234",
                        "name": "account-found-my.gov"
                    },
                    "created_on": "2014-01-01T05:20:00.12345Z",
                    "modified_on": "2014-01-01T05:20:00.12345Z",
                    "name": zone_name,
                    "name_servers": [
                        "rainbow.dns.gov",
                        "rainbow2.dns.gov",
                    ],
                    "status": "pending",
                    "tenant": {
                        "id": CloudflareService.tenant_id,
                        "name": "Fake dotgov"
                    }
                }
            }
        )


    def _mock_create_account_response(self, request):
        request_as_json = json.loads(request.content.decode('utf-8'))
        account_name = request_as_json["name"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "24681359",
                    "name": account_name,
                    "type": "standard",  # enterprise?
                    "created_on": datetime.now(timezone.utc).isoformat() # format "2014-03-01T12:21:02.0000Z",
                }
            }
        )
