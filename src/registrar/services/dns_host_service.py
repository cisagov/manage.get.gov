import logging

from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError   

logger = logging.getLogger(__name__)

class DnsHostService:

    def __init__(self):
        self.dns_vendor_service = CloudflareService()

    def _find_by_name(self, items, name):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("id") for item in items if item.get("name") == name), None)

    def dns_setup(self, account_name, zone_name):
        """Creates an account and zone in the dns host vendor tenant"""
        
        account_id = self._find_existing_account(account_name)
        has_account = bool(account_id)

        zone_id = None
        if account_id:
            zone_id = self._find_existing_zone(zone_name, account_id)
        has_zone = bool(zone_id)

        if not has_account:
            try:
                account_data = self.dns_vendor_service.create_account(account_name)
                logger.info("Successfully created account")
                account_id = account_data["result"]["id"]
            except APIError as e:
                logger.error(f"DNS setup failed to create account: {str(e)}")
                raise

            try:
                zone_data = self.dns_vendor_service.create_zone(zone_name, account_id)
                zone_name = zone_data["result"].get("name")
                logger.info(f"Successfully created zone {zone_name}")
                zone_id = zone_data["result"]["id"]
            except APIError as e:
                logger.error(f"DNS setup failed to create zone {zone_name}: {str(e)}")
                raise

        elif has_account and not has_zone:
            try:
                zone_data = self.dns_vendor_service.create_zone(zone_name, account_id)
                logger.info("Successfully created zone")
                zone_id = zone_data["result"]["id"]
            except APIError as e:
                logger.error(f"DNS setup failed to create zone {zone_name}: {str(e)}")
                raise

        return account_id, zone_id

    def create_record(self, zone_id, record_data):
        """Calls create method of vendor serivce to create a DNS record"""
        try:
            record = self.dns_vendor_service.create_dns_record(zone_id, record_data)
            logger.info(f"Created DNS record of type {record['result'].get('type')}")
        except APIError as e:
            logger.error(f"Error creating DNS record: {str(e)}")
            raise
        return record

    def _find_existing_account(self, account_name):
        try:
            all_accounts_data = self.dns_vendor_service.get_all_accounts()
            accounts = all_accounts_data['result']
            account_id = self._find_by_name(accounts, account_name)
        except APIError as e:
            logger.error(f"Error fetching accounts: {str(e)}")
            raise
        
        return account_id
    
    def _find_existing_zone(self, zone_name, account_id):
        try:
            all_zones_data = self.dns_vendor_service.get_account_zones(account_id)
            zones = all_zones_data['result']
            zone_id = self._find_by_name(zones, zone_name)
        except APIError as e:
            logger.error(f"Error fetching zones: {str(e)}")
            raise
        
        return zone_id

