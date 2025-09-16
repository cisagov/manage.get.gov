from httpx import RequestError, HTTPStatusError
import json
import logging
from django.conf import settings

from registrar.utility.errors import APIError

logger = logging.getLogger(__name__)


class CloudflareService:

    def __init__(self, client):
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.service_email = settings.SECRET_DNS_SERVICE_EMAIL
        self.tenant_key = settings.SECRET_DNS_TENANT_KEY
        self.tenant_id = settings.SECRET_DNS_TENANT_ID
        self.headers = {
            "X-Auth-Email": self.service_email,
            "X-Auth-Key": self.tenant_key,
            "Content-Type": "application/json",
        }
        client.base_url = self.base_url
        client.headers = self.headers
        self.client = client

    def create_account(self, account_name):
        appended_url = "/accounts"
        data = {"name": account_name, "type": "enterprise", "unit": {"id": self.tenant_id}}
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

    def create_zone(self, zone_name, account_id):
        appended_url = "/zones"
        data = {"name": zone_name, "account": {"id": account_id}}
        try:
            resp = self.client.post(appended_url, json=data)
            resp.raise_for_status()
            logger.info(f"Created zone {zone_name}")
        except RequestError as e:
            logger.error(f"Failed to create zone {zone_name} for account {account_id}: {e}")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while creating zone: {e}")
            raise
        return resp.json()

    def create_dns_record(self, zone_id, record_data):
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

    def get_page_accounts(self, page, per_page):
        """Gets all accounts under specified tenant. Must include pagination paramenters"""
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

    def get_account_zones(self, account_id):
        """Gets all zones under a particular account"""
        appended_url = f"/zones"
        params = f"account.id={account_id}"
        try:
            logger.info(f"Getting all account zones")
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

    def get_dns_record(self, zone_id, record_id):
        appended_url = f"/zones/{zone_id}/dns_records/{record_id}"
        try:
            resp = self.client.get(appended_url, headers=self.headers)
            logger.info("Fetching dns record. . .")
            resp.raise_for_status()
        except RequestError as e:
            logger.error("Failed to get dns record")
            raise
        except HTTPStatusError as e:
            logger.error(f"Error {e.response.status_code} while fetching dns record: {e}")
            raise
        logger.info(f"Retrieved record {record_id} from {zone_id}: {resp}")

        return resp.json()
