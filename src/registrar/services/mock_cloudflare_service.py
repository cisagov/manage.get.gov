import httpx
import json
import respx
import logging
from datetime import datetime, timezone
from faker import Faker
import re

from registrar.models import DnsZone, VendorDnsZone
from registrar.services.cloudflare_service import CloudflareService
from registrar.services.utility.dns_helper import make_dns_account_name
from registrar.services.utility.mock_cf_service_data import (
    CF_ACCOUNTS,
    CF_ACCOUNT_ZONES,
    CF_ACCOUNT_ZONES_RESULT_INFO,
    CF_ACCOUNTS_RESULT_INFO,
)
import copy

logger = logging.getLogger(__name__)

fake = Faker()


class MockCloudflareService:
    _instance = None
    _mock_context = None
    fake_zone_id = fake.uuid4().replace("-", "")  # Remove the 4 -'s in UUID4 to meet id's 32 char limit
    fake_record_id = fake.uuid4().replace("-", "")  # Remove the 4 -'s in UUID4 to meet id's 32 char limit
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
        self.__initial_state()

    def __initial_state(self):
        # using deepcopy to create copy of initial values
        self.accounts = copy.deepcopy(CF_ACCOUNTS)
        self.accounts_results_info = copy.deepcopy(CF_ACCOUNTS_RESULT_INFO)
        self.account_zones = copy.deepcopy(CF_ACCOUNT_ZONES)
        self.account_zones_result_info = copy.deepcopy(CF_ACCOUNT_ZONES_RESULT_INFO)

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

    def reset(self):
        self.__initial_state()

    def _register_account_mocks(self):
        tenant_id = CloudflareService.tenant_id
        self._mock_context.get(f"/tenants/{tenant_id}/accounts", params={"page": 1, "per_page": 50}).mock(
            side_effect=self._mock_get_page_accounts_response
        )
        self._mock_context.get(f"/tenants/{tenant_id}/accounts", params__contains={"per_page": 1}).mock(
            side_effect=self._mock_get_account_by_name_response
        )
        self._mock_context.post("/accounts").mock(side_effect=self._mock_create_account_response)

        # PATCH account dns_settings
        self._mock_context.patch(url__regex=r"/accounts/[\w-]+/dns_settings").mock(
            side_effect=self._mock_update_account_dns_settings_response
        )

    def _mock_update_account_dns_settings_response(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "zone_defaults": {
                        "zone_mode": "dns_only",
                        "nameservers": {"type": "custom.tenant"},
                    }
                },
                "success": True,
                "errors": [],
                "messages": [],
            },
        )

    def _register_zone_mocks(self):
        self._mock_context.get(url__regex=r"/zones\?account\.id=[\w-]+").mock(
            side_effect=self._mock_get_account_zones_response
        )
        self._mock_context.post("/zones").mock(side_effect=self._mock_create_cf_zone_response)
        self._mock_context.get(url__regex=r"/zones/[\w-]+").mock(side_effect=self._mock_get_cf_zone_response)

        # Mock the api with any zone id
        self._mock_context.post(url__regex=r"/zones/[\w-]+/dns_records").mock(
            side_effect=self._mock_create_dns_record_response
        )

        # Mock the api with any record id
        self._mock_context.patch(url__regex=r"/zones/[\w-]+/dns_records/[\w-]+").mock(
            side_effect=self._mock_update_dns_record_response
        )

        # PATCH account dns_settings
        self._mock_context.patch(url__regex=r"/zones/[\w-]+/dns_settings").mock(
            side_effect=self._mock_update_zone_dns_settings_response
        )

    def _mock_update_zone_dns_settings_response(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "zone_mode": "dns_only",
                    "nameservers": {"ns_set": 2, "type": "custom.tenant"},
                },
                "success": True,
                "errors": [],
                "messages": [],
            },
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
                "result": self.accounts,
                "result_info": self.accounts_results_info,
            },
        )

    def _mock_get_account_by_name_response(self, request) -> httpx.Response:
        logger.debug("😎 Mocking accounts GET by name")
        params = dict(request.url.params)
        name = params.get("name")
        matched = [a for a in self.accounts if a.get("account_pubname") == name]
        return httpx.Response(
            200,
            json={
                "errors": [],
                "messages": [],
                "success": True,
                "result": matched,
                "result_info": {"count": len(matched), "total_count": len(matched)},
            },
        )

    def _mock_get_account_zones_response(self, request) -> httpx.Response:
        logger.debug("😎 Mocking zones GET")

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": self.account_zones,
                "result_info": self.account_zones_result_info,
            },
        )

    def _mock_create_account_response(self, request) -> httpx.Response:
        logger.debug("😎 mocking account create")
        request_as_json = json.loads(request.content.decode("utf-8"))
        account_name = request_as_json["name"]
        self.new_account_id = self._mock_create_cf_id()
        created = datetime.now(timezone.utc).isoformat()  # format "2014-03-01T12:21:02.0000Z"

        # add to page account response
        self.accounts.append(
            {
                "account_tag": self.new_account_id,
                "account_pubname": account_name,
                "account_type": "standard",
                "created_on": created,
                "settings": {
                    "enforce_two_factor": False,
                    "api_access_enabled": False,
                    "access_approval_expiry": None,
                    "use_account_custom_ns_by_default": False,
                },
            }
        )

        self.accounts_results_info["count"] += 1

        # register new account to mocks
        self._register_account_mocks()

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"id": self.new_account_id, "name": account_name, "type": "standard", "created_on": created},
            },
        )

    def _mock_create_cf_zone_response(self, request) -> httpx.Response:
        logger.debug("😎 Mocking cf zone create")
        request_as_json = json.loads(request.content.decode("utf-8"))
        zone_name = request_as_json["name"]
        account_id = request_as_json["account"]["id"]
        zone_id = fake.uuid4().replace("-", "")

        # Create response dict
        result_dict = {
            "id": zone_id,
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
        }

        #  Add to account zones
        self.account_zones.append(result_dict)
        self.account_zones_result_info["count"] += 1

        # register to mocks
        self._register_zone_mocks()
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": result_dict,
            },
        )

    def _mock_get_cf_zone_response(self, request) -> httpx.Response:
        logger.debug("😃 mocking dns zone get response")

        # Get zone id from request url
        request_url = str(request.url)
        zone_id = request_url.split("/zones/")[1]
        matched = next((zone for zone in self.account_zones if zone.get("id") == zone_id), None)
        return httpx.Response(
            200,
            json={
                "errors": [],
                "messages": [],
                "success": bool(matched),
                "result": matched,
            },
        )

    def _mock_cf_error_response(self, record_name: str) -> "httpx.Response | None":
        """Return an error response for magic ``error-*`` record names, or None for success."""
        # CF validation errors — these are parsed by CloudflareService into CloudflareValidationError.
        # Use these prefixes in tests to exercise the DnsHostingError translation path.
        if record_name.startswith("error-duplicate"):
            return httpx.Response(
                400,
                json={
                    "result": None,
                    "success": False,
                    "errors": [{"code": 81057, "message": "An identical record already exists."}],
                    "messages": [],
                },
            )
        if record_name.startswith("error-conflict-cname"):
            return httpx.Response(
                400,
                json={
                    "result": None,
                    "success": False,
                    "errors": [{"code": 81053, "message": "A CNAME record with this host already exists."}],
                    "messages": [],
                },
            )
        if record_name.startswith("error-conflict-host"):
            return httpx.Response(
                400,
                json={
                    "result": None,
                    "success": False,
                    "errors": [{"code": 81053, "message": "An A or AAAA record with this host already exists."}],
                    "messages": [],
                },
            )
        if record_name.startswith("error-txt-long"):
            return httpx.Response(
                400,
                json={
                    "result": None,
                    "success": False,
                    "errors": [
                        {
                            "code": 81061,
                            "message": (
                                "Combined content length of records with this name and type"
                                " must not exceed 8192 characters."
                            ),
                        }
                    ],
                    "messages": [],
                },
            )
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
        if record_name.startswith("error"):
            return httpx.Response(500)
        return None

    def _mock_create_dns_record_response(self, request) -> httpx.Response:
        # Fields returned in the result object mirror real Cloudflare DNS record responses.
        # Keep this list in sync with what CF actually returns so tests don't silently diverge:
        #   id          — CF-assigned record UUID (generated here via _mock_create_cf_id)
        #   name        — Fully-qualified record name (apex '@' expanded to zone name)
        #   type        — Record type (A, AAAA, CNAME, MX, TXT, PTR, …)
        #   content     — Record value (IP address, hostname, text, …)
        #   ttl         — TTL in seconds (1 = automatic in CF)
        #   comment     — Optional freetext annotation
        #   priority    — MX priority (None for all other record types)
        #   proxiable   — Whether the record can be proxied (always True here)
        #   proxied     — Whether the record is currently proxied (always False here)
        #   settings    — Per-record CF settings object (empty dict)
        #   meta        — CF internal metadata (empty dict)
        #   tags        — List of string tags (empty list)
        #   created_on  — ISO-8601 timestamp
        #   modified_on — ISO-8601 timestamp
        # If CF adds new fields that our code reads, add them here to avoid silent None storage.
        logger.debug("😃 mocking dns record creation")
        request_as_json = json.loads(request.content.decode("utf-8"))
        record_name = request_as_json["name"]
        content = request_as_json["content"]
        type = request_as_json["type"]
        ttl = request_as_json.get("ttl") or 1
        comment = request_as_json.get("comment") or ""
        priority = request_as_json.get("priority")
        request_url = str(request.url)
        cf_record_name = self._convert_record_name_to_cf_record_name(record_name, request_url)

        error_response = self._mock_cf_error_response(record_name)
        if error_response is not None:
            return error_response

        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": self._mock_create_cf_id(),
                    "name": cf_record_name,
                    "type": type,
                    "content": content,
                    "proxiable": True,
                    "proxied": False,
                    "ttl": ttl,
                    "settings": {},
                    "meta": {},
                    "comment": comment,
                    "tags": [],
                    "priority": priority,
                    "created_on": datetime.now(timezone.utc).isoformat(),
                    "modified_on": datetime.now(timezone.utc).isoformat(),
                },
                "errors": [],
                "messages": [],
            },
        )

    def _mock_update_dns_record_response(self, request) -> httpx.Response:
        # Update response shape must match the create response — see the field inventory
        # in _mock_create_dns_record_response. The only difference is that the record id
        # comes from the request URL rather than being newly generated.
        logger.debug("🐟 mocking dns A record update")
        request_as_json = json.loads(request.content.decode("utf-8"))
        record_name = request_as_json["name"]
        content = request_as_json["content"]
        type = request_as_json["type"]
        ttl = request_as_json.get("ttl") or 1
        comment = request_as_json.get("comment") or ""
        priority = request_as_json.get("priority")
        # Get record id from request url to return back in response
        request_url = str(request.url)
        # Split string between "/dns_records/ and extract second partition
        record_id = request_url.split("/dns_records/")[1]
        cf_record_name = self._convert_record_name_to_cf_record_name(record_name, request_url)

        error_response = self._mock_cf_error_response(record_name)
        if error_response is not None:
            return error_response

        # Update response so it fits with whatever record we're returning
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": record_id,
                    "name": cf_record_name,
                    "type": type,
                    "content": content,
                    "proxiable": True,
                    "proxied": False,
                    "ttl": ttl,
                    "settings": {},
                    "meta": {},
                    "comment": comment,
                    "tags": [],
                    "priority": priority,
                    "created_on": datetime.now(timezone.utc).isoformat(),
                    "modified_on": datetime.now(timezone.utc).isoformat(),
                },
                "errors": [],
                "messages": [],
            },
        )

    def _mock_create_cf_id(self):
        """Create a 32 character UUID by removing the 4 -'s in a UUID4."""
        return fake.uuid4().replace("-", "")

    def _convert_record_name_to_cf_record_name(self, record_name, request_url):
        """
        Get record name in matching format to how Cloudflare stores record names.
        Root records (@) are converted to the record's zone name.
        Record names not ending in the zone name get the zone name appended to them.

        Returns None if used outside scope of DNS records page / record name not given.
        """
        try:
            zone_id = re.search("/zones/(.*)/dns_records", request_url).group(1)
            vendor_dns_zone = VendorDnsZone.objects.get(x_zone_id=zone_id)
            dns_zone = DnsZone.objects.get(vendor_dns_zone=vendor_dns_zone)
            zone_name = dns_zone.name
            if record_name == ("@"):
                record_name = zone_name
            elif not record_name.endswith(zone_name):
                record_name = f"{record_name}.{zone_name}"
            return record_name
        except Exception as e:
            logger.error(f"Failed to rename record using record's DNS zone: {e}.")
