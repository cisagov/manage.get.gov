import httpx
import respx
from faker import Faker
from random import randint
from datetime import datetime

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
        print(f"😎😎😎😎 inside register_account_mocks")
        tenant_id = CloudflareService.tenant_id
        respx.get(f"/tenants/{tenant_id}/accounts", params={"page": 1, "per_page": 50}).mock(side_effect=self._mock_get_page_accounts_response)
        respx.post(f"/accounts").mock(side_effect=self._mock_create_account_response)

    def _mock_get_page_accounts_response(self, request):
        print(f"😘😘 Using accounts mock response")
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
                    }
                },
                {
                    "account_tag": "555bbbb",
                    "account_pubname": "account-yet-another.gov",
                    "account_type": "enterprise",
                    "created_on": "2025-10-08T21:21:38.401706Z",
                    "settings": {
                        "enforce_two_factor": False,
                        "api_access_enabled": False,
                        "access_approval_expiry": None,
                        "use_account_custom_ns_by_default": False
                    }
                }
            ]}
        )

    def _mock_create_account_response(self, request):
        print(f"😘😘😘 Using mock response")
        account_name = request.content.get("name")
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "24681359",
                    "name": account_name,
                    "type": "standard",  # enterprise?
                    "created_on": datetime.now() # format "2014-03-01T12:21:02.0000Z",
                }
            }
        )
