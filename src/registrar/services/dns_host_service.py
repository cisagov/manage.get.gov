import logging

from registrar.models.domain import Domain
from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError, RegistrySystemError
from registrar.models.dns.dns_account import DnsAccount
from registrar.models.dns.dns_zone import DnsZone
from registrar.models.dns.vendor_dns_account import VendorDnsAccount
from registrar.models.dns.vendor_dns_zone import VendorDnsZone
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount as AccountsJoin
from registrar.models.dns.dns_zone_vendor_dns_zone import DnsZone_VendorDnsZone as ZonesJoin
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
            account_id = self.create_and_save_account(account_name) # Rename to account_xid
            # rename to zone_xid
            zone_id, nameservers = self.create_and_save_zone(
                domain_name, account_id
            )

        elif has_account and not has_zone:
            zone_id, nameservers = self.create_and_save_zone(
                domain_name, account_id
            )

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

    def create_and_save_zone(self, domain_name, account_id):
        try:
            zone_data = self.dns_vendor_service.create_cf_zone(domain_name, account_id)
            zone_name = zone_data["result"].get("name")
            logger.info(f"Successfully created zone {domain_name}")
            zone_id = zone_data["result"]["id"]
            nameservers = zone_data["result"].get("name_servers")

        except APIError as e:
            logger.error(f"DNS setup failed to create zone {zone_name}: {str(e)}")
            raise

        # Create zone object in registrar db
        try:
            account_id = self.save_db_zone(zone_data)
            logger.info("Successfully saved to database")
        except Exception as e:
            logger.error(f"Save to database failed: {str(e)}")
            raise
        return zone_id, nameservers

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
        per_page = 50
        page = 0
        is_last_page = False
        while is_last_page is False:
            page += 1
            try:
                page_accounts_data = self.dns_vendor_service.get_page_accounts(page, per_page)
                accounts = page_accounts_data["result"]
                account_id = self._find_by_pubname(accounts, account_name)
                if account_id:
                    break
                total_count = page_accounts_data["result_info"].get("total_count")
                is_last_page = total_count <= page * per_page

            except APIError as e:
                logger.error(f"Error fetching accounts: {str(e)}")
                raise

        return account_id

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

    def save_db_zone(self, vendor_zone_data):
        zone_data = vendor_zone_data["result"]
        zone_xid = zone_data["id"]
        zone_name = zone_data["name"]
        zone_account_name = zone_data["account"]["name"]

        with transaction.atomic():
            vendor_acc = VendorDnsZone.objects.create(
                x_zone_id=zone_xid,
                x_created_at=zone_data["created_on"],
                x_updated_at=zone_data["created_on"],
            )
            account = DnsAccount.objects.get(id=account_id)
            dns_acc = DnsAccount.objects.create(name=result["name"])

            AccountsJoin.objects.create(
                dns_account=dns_acc,
                vendor_dns_account=vendor_acc,
            )

        return zone_xid