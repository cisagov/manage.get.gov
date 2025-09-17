import json
import logging
from django.conf import settings

from registrar.utility.errors import APIError
from registrar.utility.api_helpers import make_api_request

logger = logging.getLogger(__name__)


class CloudflareService:

    def __init__(self):
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.service_email = settings.SECRET_DNS_SERVICE_EMAIL
        self.tenant_key = settings.SECRET_DNS_TENANT_KEY
        self.tenant_id = settings.SECRET_DNS_TENANT_ID
        self.headers = {
            "X-Auth-Email": self.service_email,
            "X-Auth-Key": self.tenant_key,
            "Content-Type": "application/json",
        }

    def create_account(self, account_name):
        url = f"{self.base_url}/accounts"
        data = {"name": account_name, "type": "enterprise", "unit": {"id": self.tenant_id}}
        response = make_api_request(url=url, method="POST", headers=self.headers, data=data)
        if not response["success"]:
            raise APIError(f"Failed to create account for {account_name}: {response['details']}")

        logger.info(f"Created host account: {response['data']}")

        return response["data"]

    def create_zone(self, zone_name, account_id):
        url = f"{self.base_url}/zones"
        data = {"name": zone_name, "account": {"id": account_id}}
        response = make_api_request(url=url, method="POST", headers=self.headers, data=data)
        errors = response.get("errors")
        if not response["success"]:

            raise APIError(
                f"Failed to create zone for account {account_id}: errors: {errors} message: "
                + f"{response['message']} details: {response['details']}"
            )
        logger.info(f"Created zone {zone_name} for account with id {account_id}: {response['data']}")

        return response["data"]

    def create_dns_record(self, zone_id, record_data):
        url = f"{self.base_url}/zones/{zone_id}/dns_records"
        logger.debug(f"attempting to create record for zone {zone_id} with this data: {json.dumps(record_data)}")
        response = make_api_request(url=url, method="POST", headers=self.headers, data=record_data)

        if not response["success"]:
            raise APIError(
                f"Failed to create dns record for zone {zone_id}: message: {response['message']} details:"
                + f" {response['details']}"
            )
        logger.info(f"Created dns_record for zone {zone_id}: {response['data']}")

        return response["data"]

    def get_page_accounts(self, page, per_page):
        """Gets all accounts under specified tenant. Must include pagination paramenters"""
        url = f"{self.base_url}/tenants/{self.tenant_id}/accounts?page={page}&per_page={per_page}"
        response = make_api_request(url=url, method="GET", headers=self.headers)

        if not response["success"]:
            raise APIError(f"Failed to get accounts: message: {response['message']}, details: {response['details']}")
        logger.info(f"Retrieved page accounts: {response['data']['result']}")

        return response["data"]

    def get_account_zones(self, account_id):
        """Gets all zones under a particular account"""
        url = f"{self.base_url}/zones?account.id={account_id}"
        response = make_api_request(url=url, method="GET", headers=self.headers)

        if not response["success"]:
            raise APIError(f"Failed to get zones: {response['message']}")
        logger.info(f"Retrieved all zones: {response['data']}")

        return response["data"]

    def get_dns_record(self, zone_id, record_id):
        url = f"{self.base_url}/zones/{zone_id}/dns_records/{record_id}"
        response = make_api_request(url=url, method="GET", headers=self.headers)

        if not response["success"]:
            raise APIError(f"Failed to get dns record: message: {response['message']}, details: {response['details']}")
        logger.info(f"Retrieved record {record_id} from {zone_id}: {response['data']}")

        return response["data"]
