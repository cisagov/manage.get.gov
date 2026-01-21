import logging
from django.db import IntegrityError
from registrar.models import (
    Domain,
    DnsAccount,
    VendorDnsAccount,
    DnsVendor,
    DnsZone,
    VendorDnsZone,
    DnsRecord,
    VendorDnsRecord,
    DnsAccount_VendorDnsAccount as AccountsJoin,
    DnsZone_VendorDnsZone as ZonesJoin,
    DnsRecord_VendorDnsRecord as RecordsJoin,
)
from registrar.services.utility.dns_helper import make_dns_account_name

logger = logging.getLogger(__name__)

def make_domain(**kwargs):
    """Generate a domain object"""
    domain_name = kwargs.get("domain_name", "example.gov")
    try:
        domain = Domain.objects.create(name=domain_name)
        return domain
    except IntegrityError as e:
        logger.error(f"Error creating domain. May be a duplicate. Consider creating a domain with a different name: {e}")
        raise


def make_dns_account(domain=None, **kwargs):
    """Generate a DNS account object and its vendor link"""
    domain = domain or make_domain()
    vendor = DnsVendor.objects.get(name=DnsVendor.CF)
    x_account_id = kwargs.get("x_account_id", "example_x_account_id")
    account_name = kwargs.get("account_name", make_dns_account_name(domain.name))
    try:
        dns_account = DnsAccount.objects.create(name=account_name)
    except IntegrityError as e:
        logger.error(
            f"Error creating DNS account. May be a duplicate. Consider creating an account with a different name: {e}"
        )
        raise
    x_created_at = kwargs.get("acc_x_created_at", "2025-01-01T00:00:00Z")
    x_updated_at = kwargs.get("acc_x_updated_at", "2025-01-01T00:00:00Z")

    vendor_dns_account = VendorDnsAccount.objects.create(
        dns_vendor=vendor,
        x_account_id=x_account_id,
        x_created_at=x_created_at,
        x_updated_at=x_updated_at,
    )

    dns_account.vendor_dns_account.add(vendor_dns_account)

    return dns_account


def make_zone(domain, account, **kwargs):
    """Generate a zone object and its vendor link"""
    zone_name = kwargs.get("zone_name", domain.name)
    x_zone_id = kwargs.get("x_zone_id", "example_x_zone_id")
    nameservers = kwargs.get("nameservers", ["ex1.dns.gov", "ex2.dns.gov"])
    x_created_at = kwargs.get("zone_x_created_at", "2025-01-01T00:00:00Z")
    x_updated_at = kwargs.get("zone_x_updated_at", "2025-01-01T00:00:00Z")
    try:
        dns_zone = DnsZone.objects.create(
            domain=domain,
            dns_account=account,
            name=zone_name,
            nameservers=nameservers,
        )
    except IntegrityError as e:
        logger.error(f"Error creating DNS zone. May be a duplicate. Consider creating a zone with a different name: {e}")
        raise

    vendor_dns_zone = VendorDnsZone.objects.create(
        x_zone_id=x_zone_id,
        x_created_at=x_created_at,
        x_updated_at=x_updated_at,
    )

    dns_zone.vendor_dns_zone.add(vendor_dns_zone)

    return dns_zone


def make_initial_dns_setup(domain=None, **kwargs):
    """Generate a domain, DNS account and zone object and its vendor link"""
    domain = domain or make_domain()
    dns_account = kwargs.get("dns_account", make_dns_account(domain))
    dns_zone = make_zone(domain=domain, account=dns_account, **kwargs)

    return domain, dns_account, dns_zone


def make_dns_record(zone, **kwargs):
    """Generate a DNS record object and its vendor link"""
    record_name = kwargs.get("record_name", "www")
    record_type = kwargs.get("record_type", "A")
    record_content = kwargs.get("record_content", "192.168.1.1")
    x_record_id = kwargs.get("x_record_id", "example_x_record_id")
    x_created_at = kwargs.get("record_x_created_at", "2025-01-01T00:00:00Z")
    x_updated_at = kwargs.get("record_x_updated_at", "2025-01-01T00:00:00Z")
    ttl = kwargs.get("ttl", 300)
    dns_record = DnsRecord.objects.create(
        dns_zone=zone,
        name=record_name,
        type=record_type,
        content=record_content,
        ttl=ttl,
    )
    vendor_dns_record = VendorDnsRecord.objects.create(
        name="cloudflare",
        x_record_id=x_record_id,
        x_created_at=x_created_at,
        x_updated_at=x_updated_at,
    )

    dns_record.vendor_dns_record.add(vendor_dns_record)

    return dns_record


def delete_all_dns_data():
    """Utility function to delete all DNS related data from the database"""
    VendorDnsAccount.objects.all().delete()
    DnsAccount.objects.all().delete()
    AccountsJoin.objects.all().delete()
    VendorDnsZone.objects.all().delete()
    DnsZone.objects.all().delete()
    ZonesJoin.objects.all().delete()
    Domain.objects.all().delete()
    RecordsJoin.objects.all().delete()
    VendorDnsRecord.objects.all().delete()
    DnsRecord.objects.all().delete()
