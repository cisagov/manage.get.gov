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

    def _find_nameservers_by_zone_id(self, items, x_zone_id):
        """Find an item by name in a list of dictionaries."""
        return next((item.get("name_servers") for item in items if item.get("id") == x_zone_id), None)

    def dns_setup(self, domain_name):
        account_name = make_dns_account_name(domain_name)

        x_account_id = self._find_existing_account(account_name)
        has_account = bool(x_account_id)

        x_zone_id = None
        if has_account:
            logger.info("Already has an existing vendor account")
            x_zone_id, nameservers = self._find_existing_zone(domain_name, x_account_id)
        has_zone = bool(x_zone_id)

        if not has_account:
            x_account_id = self.create_and_save_account(account_name)
            x_zone_id, nameservers = self.create_and_save_zone(domain_name, x_account_id)

        elif has_account and not has_zone:
            x_zone_id, nameservers = self.create_and_save_zone(domain_name, x_account_id)

        return x_account_id, x_zone_id, nameservers

    def create_and_save_account(self, account_name):
        try:
            account_data = self.dns_vendor_service.create_cf_account(account_name)
            logger.info("Successfully created account at vendor")
            x_account_id = account_data["result"]["id"]
        except APIError as e:
            logger.error(f"Failed to create account: {str(e)}")
            raise

        try:
            self.save_db_account(account_data)
            logger.info("Successfully saved to database")
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
            x_zone_id = zone_data["result"]["id"]
            nameservers = zone_data["result"].get("name_servers")

        except APIError as e:
            logger.error(f"DNS setup failed to create zone {zone_name}: {str(e)}")
            raise

        # Create and save zone in registrar db
        try:
            self.save_db_zone(zone_data, domain_name)
            logger.info("Successfully saved to database.")
        except Exception as e:
            logger.error(f"Failed to save zone for {domain_name} in database: {str(e)}.")
            raise
        return x_zone_id, nameservers

    def create_and_save_record(self, x_zone_id, form_record_data):
        """Calls create method of vendor service to create a DNS record"""
        # Create record in vendor service
        try:
            vendor_record_data = self.dns_vendor_service.create_dns_record(x_zone_id, form_record_data)
            logger.info(f"Created DNS record of type {vendor_record_data['result'].get('type')}")
        except APIError as e:
            logger.error(f"Error creating DNS record: {str(e)}")
            raise

        # Create and save record in registrar db
        try:
            # Do we want to save record referencing returned CF data or user input data?
            self.save_db_record(x_zone_id, vendor_record_data)
        except Exception as e:
            logger.error(f"Failed to save record {form_record_data} in database: {str(e)}.")
            raise
        return vendor_record_data

    def _find_existing_account(self, account_name):
        per_page = 50
        page = 0
        is_last_page = False
        while is_last_page is False:
            page += 1
            try:
                page_accounts_data = self.dns_vendor_service.get_page_accounts(page, per_page)
                accounts = page_accounts_data["result"]
                x_account_id = self._find_by_pubname(accounts, account_name)
                if x_account_id:
                    break
                total_count = page_accounts_data["result_info"].get("total_count")
                is_last_page = total_count <= page * per_page

            except APIError as e:
                logger.error(f"Error fetching accounts: {str(e)}")
                raise

        return x_account_id

    def _find_existing_zone(self, zone_name, x_account_id):
        try:
            all_zones_data = self.dns_vendor_service.get_account_zones(x_account_id)
            zones = all_zones_data["result"]
            x_zone_id = self._find_by_name(zones, zone_name)
            nameservers = self._find_nameservers_by_zone_id(zones, x_zone_id)
        except APIError as e:
            logger.error(f"Error fetching zones: {str(e)}")
            raise

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
        dns_vendor = DnsVendor.objects.get(name=DnsVendor.CF)

        with transaction.atomic():
            vendor_acc = VendorDnsAccount.objects.create(
                x_account_id=x_account_id,
                dns_vendor=dns_vendor,
                x_created_at=result["created_on"],
                x_updated_at=result["created_on"],
            )

            dns_acc = DnsAccount.objects.create(name=result["name"])

            AccountsJoin.objects.create(
                dns_account=dns_acc,
                vendor_dns_account=vendor_acc,
            )

    def save_db_zone(self, vendor_zone_data, domain_name):
        zone_data = vendor_zone_data["result"]
        x_zone_id = zone_data["id"]
        zone_name = zone_data["name"]
        zone_account_name = zone_data["account"]["name"]

        with transaction.atomic():
            vendor_dns_zone = VendorDnsZone.objects.create(
                x_zone_id=x_zone_id,
                x_created_at=zone_data["created_on"],
                x_updated_at=zone_data["created_on"],
            )
            dns_account = DnsAccount.objects.get(name=zone_account_name)
            dns_domain = Domain.objects.get(name=domain_name)

            dns_zone, _ = DnsZone.objects.get_or_create(dns_account=dns_account, domain=dns_domain, name=zone_name)
            # Assign ManyToMany field vendor_dns_zone manually because we cannot directly assign forward
            # side of a many to many set in Django
            # DnsZone vendor_dns_zone connected through DnsZone_VendorDnsZone so assigning vendor_dns_zone
            # automatically creates/updates its DnsZone_VendorDnsZone
            dns_zone.vendor_dns_zone.add(vendor_dns_zone)

    def save_db_record(self, x_zone_id, vendor_record_data):
        record_data = vendor_record_data["result"]
        x_record_id = record_data["id"]

        with transaction.atomic():
            vendor_dns_record = VendorDnsRecord.objects.create(
                x_record_id=x_record_id,
                x_created_at=record_data["created_on"],
                x_updated_at=record_data["created_on"],
            )

            # Find record's zone
            vendor_dns_zone = VendorDnsZone.objects.filter(x_zone_id=x_zone_id).first()
            dns_zone = ZonesJoin.objects.filter(vendor_dns_zone=vendor_dns_zone).first().dns_zone

            dns_record = DnsRecord.objects.create(
                dns_zone=dns_zone,
                type=record_data["type"],
                name=record_data["name"],
                ttl=record_data["ttl"],
                content=record_data["content"],
                comment=record_data["comment"],
                tags=record_data["tags"],
            )
            # Assign ManyToMany field vendor_dns_record manually because we cannot directly assign forward
            # side of a many to many set in Django.
            # DnsRecord vendor_dns_record connected through DnsRecord_VendorDnsRecord so assigning
            # vendor_dns_record automatically creates/updates its DnsRecord_VendorDnsRecord
            dns_record.vendor_dns_record.add(vendor_dns_record)
