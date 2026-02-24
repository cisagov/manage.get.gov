from httpx import RequestError, HTTPStatusError
from typing import Any
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class CloudflareService:
    base_url = "https://api.cloudflare.com/client/v4"
    service_email = settings.SECRET_DNS_SERVICE_EMAIL
    tenant_key = settings.SECRET_DNS_TENANT_KEY
    tenant_id = settings.SECRET_DNS_TENANT_ID
    headers = {
        "X-Auth-Email": service_email,
        "X-Auth-Key": tenant_key,
        "Content-Type": "application/json",
    }

    def __init__(self, client):
        client.base_url = self.base_url
        client.headers = self.headers
        self.client = client

    def create_cf_account(self, account_name: str):
        appended_url = "/accounts"
        data = {"name": account_name, "type": "standard", "unit": {"id": self.tenant_id}}
        try:
            resp = self.client.post(appended_url, json=data)
            resp.raise_for_status()
            logger.info(f"Created host account {account_name}")
        except RequestError as e:
            logger.error(f"Failed to create account for {account_name}: {e}")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while creating account: {e}")
            raise

        return resp.json()

    def create_cf_zone(self, zone_name: str, x_account_id: str):
        appended_url = "/zones"
        data = {"name": zone_name, "account": {"id": x_account_id}}
        try:
            resp = self.client.post(appended_url, json=data)
            resp.raise_for_status()
            logger.info(f"Created zone {zone_name}")
        except RequestError as e:
            logger.error(f"Failed to create zone {zone_name} for account {x_account_id}: {e}")
            raise
        except HTTPStatusError as e:
            error_body = e.response.text
            logger.error(
                f"Error {e.response.status_code} while creating zone {zone_name}: {e}\nResponse body: {error_body}"
            )
            raise
        return resp.json()

    def create_dns_record(self, zone_id: str, record_data: dict[str, Any]):
        appended_url = f"/zones/{zone_id}/dns_records"
        try:
            resp = self.client.post(appended_url, json=record_data)
            resp.raise_for_status()
            logger.info(f"Created dns record for zone {zone_id}")
        except RequestError as e:
            logger.error(f"Failed to create dns record for zone {zone_id}: {e}")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while creating dns record: {e}")
            raise
        return resp.json()

    def get_page_accounts(self, page: int, per_page: int):
        """Gets all accounts under specified tenant. Must include pagination parameters."""
        appended_url = f"/tenants/{self.tenant_id}/accounts"
        params = {"page": page, "per_page": per_page}
        try:
            logger.info(f"Getting all tenant accounts on page {page}")
            resp = self.client.get(appended_url, params=params)
            resp.raise_for_status()
        except RequestError as e:
            logger.error(f"Failed to get tenant accounts: {e}")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while fetching tenant accounts: {e}")
            raise
        return resp.json()

    def get_account_zones(self, x_account_id: str):
        """Gets all zones under a particular account"""
        appended_url = "/zones"
        params = f"account.id={x_account_id}"
        try:
            logger.info("Getting all of the account's zones")
            resp = self.client.get(appended_url, params=params)
            resp.raise_for_status()
        except RequestError as e:
            logger.error(f"Failed to get account zones: {e}")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while fetching account zones: {e}")
            raise
        logger.info(f"Retrieved all zones: {resp}")
        return resp.json()

    def get_dns_record(self, zone_id: str, record_id: str):
        appended_url = f"/zones/{zone_id}/dns_records/{record_id}"
        try:
            resp = self.client.get(appended_url, headers=self.headers)
            logger.info("Fetching dns record. . .")
            resp.raise_for_status()
        except RequestError as e:
            logger.error(f"Failed to get dns record {e}")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while fetching dns record: {e}")
            raise
        logger.info(f"Retrieved record {record_id} from {zone_id}: {resp}")

        return resp.json()

    def update_dns_record(self, zone_id: str, record_id: str, record_data: dict[str, Any]):
        appended_url = f"/zones/{zone_id}/dns_records/{record_id}"
        try:
            resp = self.client.patch(appended_url, headers=self.headers, json=record_data)
            resp.raise_for_status()
            logger.info(f"Updated dns record for record {record_id} in zone {zone_id}.")
        except RequestError as e:
            logger.error(f"Failed to update dns record {record_id} for zone {zone_id}: {e}")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while updating dns record: {e}")
            raise
        return resp.json()
