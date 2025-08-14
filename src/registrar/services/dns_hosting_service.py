import logging

from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError

logger = logging.getLogger(__name__)

class DnsHostingService:

    def __init__(self):
        self.dns_vendor_service = CloudflareService()

    def dns_setup(self, account_name):
        """Creates an account and zone in the dns hosting vendor tenant"""
        try:
            account_data = self.dns_vendor_service.create_account(account_name)
            logger.info("Successfully created account")
            account_id = account_data["result"]["id"]
        except APIError as e:
            logger.error(f"Error creating account in hosting service: {str(e)}")
            raise

        try:
            zone_data = self.dns_vendor_service.create_zone(account_name, account_id)
            logger.info("Successfully created zone")
            zone_id = zone_data["result"]["id"]
        except APIError as e:
            logger.error(f"Error creating account in hosting service: {str(e)}")
            raise

        return (account_id, zone_id)

    def create_record(self, zone_id, record_data):
        """Creates a DNS record"""
        try:
            record = self.dns_vendor_service.create_dns_record(zone_id, record_data)
            logger.info(f"Created DNS record of type {record["result"].get("type")}")
        except APIError as e:
            logger.error(f"Error creating dns record in hosting service: {str(e)}")

