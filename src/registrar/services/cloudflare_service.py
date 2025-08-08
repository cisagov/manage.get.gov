import logging
import requests
import settings

logger = logging.getLogger(__name__)

class CloudflareService:

    def __init__(self):
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.service_email = settings.SECRET_REGISTRY_SERVICE_EMAIL
        self.tenant_key = settings.SECRET_REGISTRY_TENANT_KEY
        self.tenant_id = settings.DOTGOV_TEST_TENANT_ACCOUNT_ID
        self.headers = {
            "X-Auth-Email": self.service_email,
            "X-Auth-Key": self.tenant_key,
            "Content-Type": "application/json",
        }
    # POST account
    def create_account(self, account_name):     
        try:
            response = requests.post(
                    f"{self.base_url}/accounts",
                    headers=self.headers,
                    json={"name": account_name, "type": "enterprise", "unit": {"id": self.tenant}},
                    timeout=5,
                )
            response_json = response.json()
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.debug("Failed to create host account", e)
        
        
        account_id = response.json()["result"]["id"]        
        logger.info(f"Created host account: {response_json}")

        return account_id

    # POST zone

    # POST dns_record