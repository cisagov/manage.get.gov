import os
import requests


class BaoClient: 
    def __init__(self):
        self.base_url = os.environ["VAULT_ADDR"]
        self.headers = {"X-Vault-Token": os.environ["VAULT_TOKEN"]}

    def store_secret(self, path, data):
        response = requests.post(
            f"{self.base_url}/v1/secret/data/{path}",
            headers=self.headers,
            json={"data":data},
        )
        response.raise_for_status()
        return response.json()
    
    def get_secret(self, path):
        response = requests.get(
            f"{self.base_url}/v1/secret/data/{path}",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()["data"]["data"]
    
    def delete_secret(self, path):
        response = requests.delete(
            f"{self.base_url}/v1/secret/data/{path}",
            headers=self.headers,
        )
        response.raise_for_status()
    
    def store_global_api_key(self, api_key):
        self.store_secret("global/cloudflare_api_key", {"api_key": api_key})
    
    def get_global_api_key(self):
        return self.get_secret("global/cloudflare_api_key")["api_key"]

    def store_account_tokens(self, account_id, tokens: dict):
        """
        tokens = {
            "create_token": "...",
            "settings_write": "...",
            "settings_read": "...",
            "dns_write": "...",
            "dns_read": "...",
        }
        """

        for token_name, token_value in tokens.items():
            self.store_secret(
                f"accounts/{account_id}/{token_name}",
                {"token": token_value}
            )
    
    def get_account_token(self, account_id, token_name):
        return self.get_secret(
            f"accounts/{account_id}/{token_name}"
        )["token"]
    
    def delete_account_tokens(self, account_id):
        token_names = [
            "create_token", "settings_write", "settings_read", 
            "dns_write", "dns_read"
        ]

        for token_name in token_names:
            self.delete_secret(f"accounts/{account_id}/{token_name}")