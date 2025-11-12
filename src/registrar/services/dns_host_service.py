import logging

from registrar.models.domain import Domain
from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError, RegistrySystemError
from registrar.models.dns.dns_account import DnsAccount
from registrar.models.dns.vendor_dns_account import VendorDnsAccount
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount as AccountsJoin
from registrar.models.dns.dns_vendor import DnsVendor

from django.db import transaction
from registrar.services.utility.dns_helper import make_dns_account_name


logger = logging.getLogger(__name__)


class DnsHostService:

    def __init__(self, client):
        self.dns_vendor_service = CloudflareService(client)

    def _find_by_pubname(self, items, name):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("account_tag") for item in items if item.get("account_pubname") == name), None)

    def _find_by_name(self, items, name):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("id") for item in items if item.get("name") == name), None)

    def _find_nameservers_by_zone_id(self, items, zone_id):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("name_servers") for item in items if item.get("id") == zone_id), None)

    def dns_setup(self, domain_name):
        account_name = make_dns_account_name(domain_name)

        account_id = self._find_existing_account(account_name)
        has_account = bool(account_id)

        zone_id = None
        if has_account:
            logger.info("Already has an existing vendor account")
            zone_id, nameservers = self._find_existing_zone(domain_name, account_id)
        has_zone = bool(zone_id)

        if not has_account:
            account_id = self.create_and_save_account(account_name)

            try:
                zone_data = self.dns_vendor_service.create_zone(domain_name, account_id)
                zone_name = zone_data["result"].get("name")
                logger.info(f"Successfully created zone {domain_name}")
                zone_id = zone_data["result"]["id"]
                nameservers = zone_data["result"].get("name_servers")

            except APIError as e:
                logger.error(f"DNS setup failed to create zone {zone_name}: {str(e)}")
                raise

        elif has_account and not has_zone:
            try:
                zone_data = self.dns_vendor_service.create_zone(domain_name, account_id)
                logger.info("Successfully created zone")
                zone_name = zone_data["result"].get("name")
                zone_id = zone_data["result"]["id"]
                nameservers = zone_data["result"].get("name_servers")

            except APIError as e:
                logger.error(f"DNS setup failed to create zone {domain_name}: {str(e)}")
                raise

        return account_id, zone_id, nameservers

    def create_and_save_account(self, account_name):
        try:
            account_data = self.dns_vendor_service.create_cf_account(account_name)
            logger.info("Successfully created account at vendor")
            account_id = account_data["result"]["id"]
        except APIError as e:
            logger.error(f"Failed to create account: {str(e)}")
            raise

        try:
            account_id = self.save_db_account(account_data)
            logger.info("Successfully saved to database")
        except Exception as e:
            logger.error(f"Save to database failed: {str(e)}")
            raise

        return account_id

    def create_record(self, zone_id, record_data):
        """Calls create method of vendor service to create a DNS record"""
        try:
            record = self.dns_vendor_service.create_dns_record(zone_id, record_data)
            logger.info(f"Created DNS record of type {record['result'].get('type')}")
        except APIError as e:
            logger.error(f"Error creating DNS record: {str(e)}")
            raise
        return record

    def _find_existing_account(self, account_name):
        dns_account = DnsAccount.objects.filter("name=account_name").first()
        if not dns_account:
            return None

        db_account_id = (
            AccountsJoin.objects.filter(dns_account=dns_account, is_active=True)
            .values_list("vendor_dns_account__x_account_id", flat=True)
            .first()
        )

        if db_account_id:
            per_page = 50
            page = 0
            is_last_page = False
            while is_last_page is False:
                page += 1
                try:
                    page_accounts_data = self.dns_vendor_service.get_page_accounts(page, per_page)
                    accounts = page_accounts_data["result"]
                    cf_account_id = self._find_by_pubname(accounts, account_name)
                    if cf_account_id:
                        break
                    total_count = page_accounts_data["result_info"].get("total_count")
                    is_last_page = total_count <= page * per_page

                except APIError as e:
                    logger.error(f"Error fetching accounts: {str(e)}")
                    raise

        if cf_account_id and cf_account_id == db_account_id:
            return db_account_id

        elif cf_account_id and cf_account_id != db_account_id:
            logger.warning(
                "Cloudflare id mismatch for '%s': DB has %s, CF returned %s", account_name, db_account_id, cf_account_id
            )

        return None

    def _find_existing_zone(self, zone_name, account_id):
        try:
            all_zones_data = self.dns_vendor_service.get_account_zones(account_id)
            zones = all_zones_data["result"]
            zone_id = self._find_by_name(zones, zone_name)
            nameservers = self._find_nameservers_by_zone_id(zones, zone_id)
        except APIError as e:
            logger.error(f"Error fetching zones: {str(e)}")
            raise

        return zone_id, nameservers

    def register_nameservers(self, domain_name, nameservers):
        domain = Domain.objects.get(name=domain_name)
        # TODO: first check domain state? or status? to ensure it's in the registry?
        nameserver_tups = [tuple([n]) for n in nameservers]

        try:
            logger.info("Attempting to register nameservers. . .")
            domain.nameservers = nameserver_tups  # calls EPP service to post nameservers to registry
        except (RegistrySystemError, Exception):
            raise

    def save_db_account(self, vendor_account_data):
        result = vendor_account_data["result"]
        account_id = result["id"]
        dns_vendor = DnsVendor.objects.get(name=DnsVendor.CF)

        with transaction.atomic():
            vendor_acc = VendorDnsAccount.objects.create(
                x_account_id=account_id,
                dns_vendor=dns_vendor,
                x_created_at=result["created_on"],
                x_updated_at=result["created_on"],
            )

            dns_acc = DnsAccount.objects.create(name=result["name"])

            AccountsJoin.objects.create(
                dns_account=dns_acc,
                vendor_dns_account=vendor_acc,
            )

        return account_id
