import logging

from registrar.models.domain import Domain
from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import APIError, RegistrySystemError
from registrar.models import (
    DnsVendor,
    DnsAccount,
    DnsZone,
    DnsRecord,
    VendorDnsAccount,
    VendorDnsZone,
    VendorDnsRecord,
    DnsAccount_VendorDnsAccount as AccountsJoin,
    DnsZone_VendorDnsZone as ZonesJoin,
    DnsRecord_VendorDnsRecord as RecordsJoin,
)
from registrar.utility.constants import CURRENT_DNS_VENDOR
from django.db import transaction
from registrar.services.utility.dns_helper import make_dns_account_name

logger = logging.getLogger(__name__)


class DnsHostService:

    def __init__(self, client):
        self.dns_vendor_service = CloudflareService(client)

    def _find_account_tag_by_pubname(self, items, name):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("account_tag") for item in items if item.get("account_pubname") == name), None)

    def _find_account_json_by_pubname(self, items, name):
        return next((item for item in items if item.get("account_pubname") == name), None)

    def _find_zone_json_by_name(self, items, name):
        return next((item for item in items if item.get("name") == name), None)

    def _find_id_by_name(self, items, name):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("id") for item in items if item.get("name") == name), None)

    def _find_nameservers_by_zone_id(self, items, x_zone_id):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("name_servers") for item in items if item.get("id") == x_zone_id), None)

    def dns_account_setup(self, domain_name):
        """
        Ensure a DNS Vendor account exists for this domain and is saved to the database.
        Returns x_account_id.
        """
        account_name = make_dns_account_name(domain_name)

        x_account_id = self._find_existing_account_in_db(account_name)
        has_db_account = bool(x_account_id)
        if has_db_account:
            logger.info("Already has an existing vendor account")
            return x_account_id

        cf_account_data = self._find_existing_account_in_cf(account_name)
        has_cf_account = bool(cf_account_data)
        if has_cf_account:
            return self.save_db_account({"result": cf_account_data})

        logger.info(f"Account setup completed successfully for account for {domain_name}")
        return self.create_and_save_account(account_name)

    def dns_zone_setup(self, domain_name, x_account_id):
        """
        Ensure a DNS Vendor zone exists for this domain and is saved to the database.
        """
        has_zone = DnsZone.objects.filter(name=domain_name).exists()
        if has_zone:
            logger.info("Already has an existing zone and nameservers")
            return

        try:
            zone_data = self._find_existing_zone_in_cf(domain_name, x_account_id)
        except APIError as e:
            logger.error(e)
            raise

        if zone_data:
            self.save_db_zone({"result": zone_data}, domain_name)
        else:
            try:
                self.create_and_save_zone(domain_name, x_account_id)
            except Exception as e:
                logger.error(f"dnsSetup for zone failed {e}")
                raise

        logger.info(f"Zone setup completed successfully for domain {domain_name}")
        return

    def create_and_save_account(self, account_name) -> str:
        try:
            account_data = self.dns_vendor_service.create_cf_account(account_name)
            logger.info("Successfully created account at vendor")
            x_account_id = account_data["result"]["id"]
        except APIError as e:
            logger.error(f"Failed to create account: {str(e)}")
            raise

        try:
            self.save_db_account(account_data)
            logger.info(f"Successfully saved account '{account_name}' to database")
        except Exception as e:
            logger.error(f"Failed to save {account_name} to database: {str(e)}")
            raise

        return x_account_id

    def create_and_save_zone(self, domain_name, x_account_id):
        # Create zone in vendor service
        try:
            zone_data = self.dns_vendor_service.create_cf_zone(domain_name, x_account_id)
            zone_name = zone_data["result"].get("name")
            logger.info(f"Successfully created zone {domain_name}.")

        except APIError as e:
            logger.error(f"DNS setup failed to create zone {zone_name}: {str(e)}")
            raise

        # Create and save zone in registrar db
        try:
            self.save_db_zone(zone_data, domain_name)
            logger.info(f"Successfully saved zone '{domain_name}' to database")
        except Exception as e:
            logger.error(f"Failed to save zone for {domain_name} in database: {str(e)}.")
            raise

    def create_and_save_record(self, x_zone_id, form_record_data) -> dict:
        """Calls create method of vendor service to create a DNS record"""
        # Create record in vendor service
        try:
            vendor_record_data = self.dns_vendor_service.create_dns_record(x_zone_id, form_record_data)
            logger.info(f"Created DNS record of type {vendor_record_data['result'].get('type')}")
        except APIError as e:
            logger.error(f"Error creating DNS record: {str(e)}")
            raise

        # Create and save dns record in registrar db
        try:
            self.save_db_record(x_zone_id, vendor_record_data)
        except Exception as e:
            logger.error(f"Failed to save record {form_record_data} in database: {str(e)}.")
            raise
        return vendor_record_data

    def _find_existing_account_in_cf(self, account_name) -> dict | None:
        per_page = 50
        page = 0
        is_last_page = False
        while is_last_page is False:
            page += 1
            try:
                page_accounts_data = self.dns_vendor_service.get_page_accounts(page, per_page)
                accounts = page_accounts_data["result"]
                account_data = self._find_account_json_by_pubname(accounts, account_name)
                if account_data:
                    break
                total_count = page_accounts_data["result_info"].get("total_count")
                is_last_page = total_count <= page * per_page

            except APIError as e:
                logger.error(f"Error fetching accounts: {str(e)}")
                raise

        return account_data

    def _find_existing_account_in_db(self, account_name) -> str | None:
        try:
            dns_account = DnsAccount.objects.get(name=account_name)
        except DnsAccount.DoesNotExist:
            logger.debug(f"No db account found by name {account_name}")
            return None

        return dns_account.get_active_x_account_id()

    def _find_existing_zone_in_cf(self, zone_name, x_account_id) -> dict | None:
        try:
            all_zones_data = self.dns_vendor_service.get_account_zones(x_account_id)
            zones = all_zones_data["result"]
            zone_data = self._find_zone_json_by_name(zones, zone_name)
        except APIError as e:
            logger.error(f"Error fetching zones: {str(e)}")
            raise

        return zone_data

    def get_x_zone_id_if_zone_exists(self, domain_name) -> tuple[str | None, list[str] | None]:
        # returns x_zone_id (and temporarily returns nameservers)
        try:
            zone = DnsZone.objects.get(name=domain_name)
        except DnsZone.DoesNotExist:
            logger.debug(f"Zone for domain {domain_name} does not exist")
            return None, None

        x_zone_id = zone.get_active_x_zone_id()
        nameservers = zone.nameservers or []

        # temporarily returning nameservers until we retrieve nameservers directly
        return x_zone_id, nameservers

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
        x_account_id = result["id"]
        dns_vendor = DnsVendor.objects.get(name=CURRENT_DNS_VENDOR)

        # TODO: handle transaction failure
        try:
            with transaction.atomic():
                vendor_acc,_ = VendorDnsAccount.objects.get_or_create(
                    x_account_id=x_account_id,
                    dns_vendor=dns_vendor,
                    defaults={
                        "x_created_at": result["created_on"],
                        "x_updated_at": result["created_on"]
                    }
                )

                dns_acc = DnsAccount.objects.create(name=result["name"])

                AccountsJoin.objects.create(
                    dns_account=dns_acc,
                    vendor_dns_account=vendor_acc,
                )

        except Exception as e:
            logger.error(f"Failed to save account to database: {str(e)}.")
            raise

    def save_db_zone(self, vendor_zone_data, domain_name):
        zone_data = vendor_zone_data["result"]
        x_zone_id = zone_data["id"]
        zone_name = zone_data["name"]
        zone_account_name = zone_data["account"]["name"]
        nameservers = zone_data["vanity_name_servers"] or zone_data["name_servers"]

        # TODO: handle transaction failure
        try:
            with transaction.atomic():
                vendor_dns_zone = VendorDnsZone.objects.create(
                    x_zone_id=x_zone_id,
                    x_created_at=zone_data["created_on"],
                    x_updated_at=zone_data["created_on"],
                )

                dns_account = DnsAccount.objects.get(name=zone_account_name)
                dns_domain = Domain.objects.get(name=domain_name)

                dns_zone = DnsZone.objects.create(
                    dns_account=dns_account, domain=dns_domain, name=zone_name, nameservers=nameservers
                )

                ZonesJoin.objects.create(dns_zone=dns_zone, vendor_dns_zone=vendor_dns_zone)
        except Exception as e:
            logger.error(f"Failed to save zone to database: {str(e)}.")
            raise

    def save_db_record(self, x_zone_id, vendor_record_data):
        record_data = vendor_record_data["result"]
        x_record_id = record_data["id"]

        try:
            with transaction.atomic():
                vendor_dns_record = VendorDnsRecord.objects.create(
                    x_record_id=x_record_id,
                    x_created_at=record_data["created_on"],
                    x_updated_at=record_data["created_on"],
                )

                # Find record's zone
                vendor_dns_zone = VendorDnsZone.objects.filter(x_zone_id=x_zone_id).first()
                dns_zone = vendor_dns_zone.zone_link.get(is_active=True).dns_zone

                dns_record = DnsRecord.objects.create(
                    dns_zone=dns_zone,
                    type=record_data["type"],
                    name=record_data["name"],
                    ttl=record_data["ttl"],
                    content=record_data["content"],
                    comment=record_data["comment"],
                    tags=record_data["tags"],
                )

                RecordsJoin.objects.create(
                    dns_record=dns_record,
                    vendor_dns_record=vendor_dns_record,
                )

        except Exception as e:
            logger.error(f"Failed to save record to database: {str(e)}.")
            raise
