import logging
from django.conf import settings

from registrar.utility.errors import APIError
from registrar.utility.api_helpers import make_api_request

logger = logging.getLogger(__name__)

class CloudflareService:

    def __init__(self):
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.service_email = settings.SECRET_REGISTRY_SERVICE_EMAIL
        self.tenant_key = settings.SECRET_REGISTRY_TENANT_KEY
        self.tenant_id = settings.SECRET_DOTGOV_TENANT_ID
        self.headers = {
            "X-Auth-Email": self.service_email,
            "X-Auth-Key": self.tenant_key,
            "Content-Type": "application/json",
        }
    # POST account
    def create_account(self, account_name):     
        url = f"{self.base_url}/accounts"
        data = {"name": account_name, "type": "enterprise", "unit": {"id": self.tenant_id}}
        response = make_api_request(url=url, method="POST", headers=self.headers, data=data )
        if not response['success']:
            raise APIError(f"Failed to create account for {account_name}: {response['message']}")
               
        logger.info(f"Created host account: {response['data']}")

        return response['data']

    # POST zone
    def create_zone(self, account_name, account_id):     
        url = f"{self.base_url}/zones"
        data = {"name": account_name, "account": {"id": account_id }}
        response = make_api_request(url=url, method="POST", headers=self.headers, data=data )

        if not response['success']:
            raise APIError(f"Failed to create zone for {account_name}: {response['message']}")
        logger.info(f"Created zone for account {account_name}: {response['data']}")

        return response['data']

    # POST dns_record
    def create_dns_record(self, zone_id, record_data):
        url = f"{self.base_url}/zones/{zone_id}/dns_record"
        response = make_api_request(url=url, method="POST", headers=self.headers, data=record_data )

        if not response['success']:
            raise APIError(f"Failed to create dns record for zone {zone_id}: {response['message']}")             
        logger.info(f"Created dns_record for zone {zone_id}: {response['data']}")

        return response['data']
    
    # GET accounts
    def get_all_accounts(self):
        '''Gets all accounts under all(?!) tenants'''
        url = f"{self.base_url}/accounts"
        response = make_api_request(url=url, method="GET", headers=self.headers )

        if not response['success']:
            raise APIError(f"Failed to get accounts: {response['message']}")             
        logger.info(f"Retrieved all accounts: {response['data']}")

        return response['data']
    
    # GET zones
    def get_all_zones(self):
        '''Gets all zones under all(?!) tenants'''
        url = f"{self.base_url}/accounts"
        response = make_api_request(url=url, method="GET", headers=self.headers )

        if not response['success']:
            raise APIError(f"Failed to get zones: {response['message']}")             
        logger.info(f"Retrieved all zones: {response['data']}")

        return response['data']
 
    # GET dns record for zone
    def get_dns_record(self, zone_id, record_id):
        url = f"{self.base_url}/zones/{zone_id}/dns_records/{record_id}"
        response = make_api_request(url=url, method="GET", headers=self.headers )

        if not response['success']:
            raise APIError(f"Failed to get dns record: {response['message']}")             
        logger.info(f"Retrieved record {record_id} from {zone_id}: {response['data']}")

        return response['data']
    