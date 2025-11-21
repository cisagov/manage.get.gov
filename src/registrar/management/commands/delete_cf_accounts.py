#!/usr/bin/env python3
"""
Cloudflare Tenant Account Deletion Script
Provides options to delete accounts under the test tenant via Cloudflare API
"""

import argparse
import os
from django.core.management import BaseCommand
from django.conf import settings
import httpx
import sys
from typing import List


class Command(BaseCommand):
    help = "Deletes Cloudflare accounts for the test tenant based on account name(s) or account id(s)"

    def __init__(self):
        super().__init__()
        """Initialize with Cloudflare credentials and tenant ID"""
        self.email = settings.SECRET_DNS_SERVICE_EMAIL
        self.api_key = settings.SECRET_DNS_TENANT_KEY
        self.tenant_id = os.environ.get(
            "DNS_TEST_TENANT_ID"
        )  # We only ever want to delete from the test tenant DO NOT USE THE PROD TENANT ID
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {"X-Auth-Email": self.email, "X-Auth-Key": self.api_key, "Content-Type": "application/json"}

    def get_tenant_accounts(self, per_page: int = 50) -> List[dict]:
        """Fetch all accounts under the tenant with pagination"""
        all_accounts = []
        page = 1
        is_last_page = False

        while True:
            url = f"{self.base_url}/tenants/{self.tenant_id}/accounts"
            params = {"page": page, "per_page": per_page}

            response = httpx.get(url, headers=self.headers, params=params)

            if response.status_code != 200:
                print(f"Error fetching accounts (page {page}): {response.status_code}")
                print(response.text)
                break

            data = response.json()

            if not data.get("success"):
                print(f"API returned error: {data.get('errors', 'Unknown error')}")
                break

            accounts = data.get("result", [])

            if not accounts:
                # No more accounts to fetch
                break

            all_accounts.extend(accounts)

            # Check if there are more pages
            result_info = data.get("result_info", {})
            total_count = result_info.get("total_count", 1)
            is_last_page = total_count <= page * per_page
            if is_last_page:
                break

            page += 1

        return all_accounts

    def delete_account(self, account_id: str) -> bool:
        """Delete a single account by ID"""
        url = f"{self.base_url}/accounts/{account_id}"
        response = httpx.delete(url, headers=self.headers)

        if response.status_code in [200, 204]:
            print(f"✓ Successfully deleted account: {account_id}")
            return True
        else:
            print(f"✗ Failed to delete account {account_id}: {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    def delete_all_accounts(self, dry_run: bool = False) -> None:
        """Delete all accounts under the tenant"""
        print(f"Fetching all accounts under tenant {self.tenant_id}...")
        accounts = self.get_tenant_accounts()

        if not accounts:
            print("No accounts found or error fetching accounts.")
            return

        print(f"Found {len(accounts)} account(s)")

        if dry_run:
            print("\n[DRY RUN] Would delete the following accounts:")
            for acc in accounts:
                print(f"  - {acc['account_tag']}: {acc.get('account_pubname', 'Unnamed')}")
            return

        confirm = input(f"\nAre you sure you want to delete ALL {len(accounts)} accounts? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            return

        for account in accounts:
            self.delete_account(account["account_tag"])

    def delete_by_ids(self, account_ids: List[str], dry_run: bool = False) -> None:
        """Delete multiple accounts by list of IDs"""
        if dry_run:
            print(f"[DRY RUN] Would delete {len(account_ids)} account(s):")
            for acc_id in account_ids:
                print(f"  - {acc_id}")
            return

        print(f"Deleting {len(account_ids)} account(s)...")
        for account_id in account_ids:
            self.delete_account(account_id)

    def delete_by_names(self, account_names: List[str], dry_run: bool = False) -> None:
        """Delete accounts by list of names"""
        print(f"Fetching all accounts under tenant {self.tenant_id}...")
        accounts = self.get_tenant_accounts()

        if not accounts:
            print("No accounts found or error fetching accounts.")
            return

        # Find accounts matching any of the names
        name_set = set(account_names)
        matching_accounts = [acc for acc in accounts if acc.get("account_pubname") in name_set]

        if not matching_accounts:
            print("No accounts found with the specified names")
            return

        print(f"Found {len(matching_accounts)} account(s) matching the provided names:")
        for acc in matching_accounts:
            print(f"  - {acc['account_tag']}: {acc.get('account_pubname', 'Unnamed')}")

        if dry_run:
            print("\n[DRY RUN] Would delete the above account(s)")
            return

        confirm = input(
            f"\nDelete {len(matching_accounts)} account(s), including if multiple accounts with the same name?(yes/no):"
        )
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            return

        for account in matching_accounts:
            self.delete_account(account["account_tag"])

    def delete_all_except_ids(self, except_ids: List[str], dry_run: bool = False) -> None:
        """Delete all accounts under tenant except the specified list"""
        print(f"Fetching all accounts under tenant {self.tenant_id}...")
        accounts = self.get_tenant_accounts()

        if not accounts:
            print("No accounts found or error fetching accounts.")
            return

        except_set = set(except_ids)
        to_delete = [acc for acc in accounts if acc["account_tag"] not in except_set]

        if not to_delete:
            print("No accounts to delete (all accounts are in the exception list).")
            return

        print(f"Found {len(to_delete)} account(s) to delete (keeping {len(except_ids)} account(s))")

        if dry_run:
            print("\n[DRY RUN] Would delete the following accounts:")
            for acc in to_delete:
                print(f"  - {acc['account_tag']}: {acc.get('account_pubname', 'Unnamed')}")
            print("\n[DRY RUN] Would keep the following accounts:")
            for acc_id in except_ids:
                print(f"  - {acc_id}")
            return

        confirm = input(f"\nDelete {len(to_delete)} account(s), keeping {len(except_ids)}? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            return

        for account in to_delete:
            self.delete_account(account["account_tag"])

    def add_arguments(self, parser):
        parser.description = "Delete Cloudflare accounts under a tenant via API"
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
            Environment Variables:
            DNS_SERVICE_EMAIL: Cloudflare account email
            DNS_TENANT_KEY: Cloudflare API key
            DNS_TEST_TENANT_ID: Unique ID associated with Cloudflare tenant

            %(prog)s --all

            # Using command line arguments
            %(prog)s --all

            # Delete multiple accounts by ids
            %(prog)s --ids abc123 def456 ghi789

            # Delete multiple accounts by names
            %(prog)s --names "Dev Account" "Test Account" "Staging"

            # Delete all except multiple accounts
            %(prog)s --all-except-ids abc123 def456 ghi789

            # Dry run (preview without deleting)
            %(prog)s --all --dry-run
                    """

        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--all", action="store_true", help="Delete all accounts under the tenant")
        group.add_argument("--ids", nargs="+", help="Delete multiple accounts by IDs")
        group.add_argument("--names", nargs="+", help="Delete multiple accounts by names")
        group.add_argument("--all-except-ids", nargs="+", help="Delete all accounts except these IDs")

        parser.add_argument("--dry-run", action="store_true", help="Preview operation without actually deleting")

    def handle(self, **options):
        try:
            if options.get("all"):
                self.delete_all_accounts(dry_run=options["dry_run"])
            elif options.get("ids"):
                self.delete_by_ids(options["ids"], dry_run=options["dry_run"])
            elif options.get("names"):
                self.delete_by_names(options["names"], dry_run=options["dry_run"])
            elif options.get("all_except_ids"):
                self.delete_all_except_ids(options["all_except_ids"], dry_run=options["dry_run"])
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            sys.exit(1)
        except Exception as e:
            print(f"\nError: {e}")
            sys.exit(1)
