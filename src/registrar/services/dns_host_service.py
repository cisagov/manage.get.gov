import logging

from registrar.models.domain import Domain
from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError, RegistrySystemError
from registrar.models.dns.dns_account import DnsAccount
from registrar.models.dns.vendor_dns_account import VendorDnsAccount
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount as Join
from registrar.models.dns.dns_vendor import DnsVendor

from django.db import transaction, connection
from django.utils import timezone

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

    def dns_setup(self, account_name, domain_name):
        """Creates an account and zone in the dns host vendor tenant. Registers nameservers after zone creation"""

        account_id = self._find_existing_account(account_name)
        has_account = bool(account_id)

        zone_id = None
        if account_id:
            zone_id, nameservers = self._find_existing_zone(domain_name, account_id)
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
                account_id = self.create_db_account(account_data)
            except Exception as e:
                logger.error("Save to database failed")
                raise

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
            domain.nameservers = nameserver_tups  # calls epp service to post nameservers to registry
        except (RegistrySystemError, Exception):
            raise

    def create_db_account(self, account_data):
        result = account_data["result"]
        account_id = result["id"]
        dns_vendor = DnsVendor.objects.get(name=DnsVendor.CF)

        with transaction.atomic():
            vendor_acc = VendorDnsAccount.objects.create(
                x_account_id=account_id,
                dns_vendor=dns_vendor,
                x_created_at = result["created_on"],
                x_updated_at = result["created_on"],
            )
            logger.info("VendorAccount saved: id=%s, name=%s", vendor_acc.pk, vendor_acc.x_account_id)

            dns_acc = DnsAccount.objects.create(name=result["name"])
            logger.info("DnsAccount saved: id=%s, name=%s", dns_acc.pk, dns_acc.name)

            join = Join.objects.create(
                dns_account=dns_acc,
                vendor_dns_account=vendor_acc,
            )
            logger.info(
                "Join link saved: dns_account_id=%s, vendor_dns_account_id=%s is_active=%s",
                dns_acc.pk,
                vendor_acc.pk,
                join.is_active,
            )

            logger.info("DB settings: %s", connection.settings_dict)

        return account_id
