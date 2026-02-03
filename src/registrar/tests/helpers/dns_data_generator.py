from datetime import datetime
import logging
from django.db import IntegrityError
from registrar.models import (
    Domain,
    DomainInformation,
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
    User,
)
from registrar.services.utility.dns_helper import make_dns_account_name

logger = logging.getLogger(__name__)


def get_user():
    user, created = User.objects.get_or_create(
        username="dns_host_test_user",
        email="dns_test@dot.gov",
    )

    return user


def create_domain(**kwargs):
    """Generate a domain object"""
    domain_name = kwargs.get("domain_name", "example.gov")
    test_user = get_user()

    try:
        domain = Domain.objects.create(name=domain_name)
        DomainInformation.objects.get_or_create(requester=test_user, domain=domain)
        return domain
    except IntegrityError as e:
        logger.error(
            f"Error creating domain. May be a duplicate. Consider creating a domain with a different name: {e}"
        )
        raise


def create_dns_account(domain, **kwargs):
    """Generate DNS and vendor account objects and their link"""
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

    default_datetime = datetime(2026, 1, 19, 12, 0, 0)
    x_created_at = kwargs.get("acc_x_created_at", default_datetime)
    x_updated_at = kwargs.get("acc_x_updated_at", default_datetime)

    vendor_dns_account = VendorDnsAccount.objects.create(
        dns_vendor=vendor,
        x_account_id=x_account_id,
        x_created_at=x_created_at,
        x_updated_at=x_updated_at,
    )

    is_active = kwargs.get("acc_is_active", True)
    AccountsJoin.objects.create(
        dns_account=dns_account,
        vendor_dns_account=vendor_dns_account,
        is_active=is_active,
    )

    return dns_account


def create_dns_zone(domain, account, **kwargs):
    """Generate zone objects and their link"""
    zone_name = kwargs.get("zone_name", domain.name)
    x_zone_id = kwargs.get("x_zone_id", "example_x_zone_id")
    nameservers = kwargs.get("nameservers", ["ex1.dns.gov", "ex2.dns.gov"])
    vanity_nameservers = kwargs.get("vanity_nameservers", [])
    default_datetime = datetime(2026, 1, 19, 12, 0, 0)
    x_created_at = kwargs.get("zone_x_created_at", default_datetime)
    x_updated_at = kwargs.get("zone_x_updated_at", default_datetime)

    nameservers_to_use = vanity_nameservers or nameservers

    try:
        dns_zone = DnsZone.objects.create(
            domain=domain,
            dns_account=account,
            name=zone_name,
            nameservers=nameservers_to_use,
        )
    except IntegrityError as e:
        logger.error(
            f"Error creating DNS zone. May be a duplicate. Consider creating a zone with a different name: {e}"
        )
        raise

    vendor_dns_zone = VendorDnsZone.objects.create(
        x_zone_id=x_zone_id,
        x_created_at=x_created_at,
        x_updated_at=x_updated_at,
    )

    is_active = kwargs.get("zone_is_active", True)
    ZonesJoin.objects.create(
        dns_zone=dns_zone,
        vendor_dns_zone=vendor_dns_zone,
        is_active=is_active,
    )

    return dns_zone


def create_initial_dns_setup(domain=None, **kwargs):
    """Generate a domain, account objects and zone object and their links"""
    domain = domain or create_domain()
    dns_account = kwargs.get("dns_account", create_dns_account(domain))
    dns_zone = create_dns_zone(domain=domain, account=dns_account, **kwargs)

    return domain, dns_account, dns_zone


def create_dns_record(zone, **kwargs):
    """Generate a DNS record object and its vendor link"""
    record_name = kwargs.get("record_name", "www")
    record_type = kwargs.get("record_type", "A")
    record_content = kwargs.get("record_content", "192.168.1.1")
    x_record_id = kwargs.get("x_record_id", "example_x_record_id")
    default_datetime = datetime(2026, 1, 19, 12, 0, 0)
    x_created_at = kwargs.get("record_x_created_at", default_datetime)
    x_updated_at = kwargs.get("record_x_updated_at", default_datetime)
    ttl = kwargs.get("ttl", 300)
    dns_record = DnsRecord.objects.create(
        dns_zone=zone,
        name=record_name,
        type=record_type,
        content=record_content,
        ttl=ttl,
    )
    vendor_dns_record = VendorDnsRecord.objects.create(
        x_record_id=x_record_id,
        x_created_at=x_created_at,
        x_updated_at=x_updated_at,
    )

    is_active = kwargs.get("dns_record_is_active", True)
    RecordsJoin.objects.create(
        dns_record=dns_record,
        vendor_dns_record=vendor_dns_record,
        is_active=is_active,
    )

    return dns_record


def delete_all_dns_data():
    """Utility function to delete all DNS related data from the database"""
    RecordsJoin.objects.all().delete()
    VendorDnsRecord.objects.all().delete()
    DnsRecord.objects.all().delete()
    VendorDnsZone.objects.all().delete()
    DnsZone.objects.all().delete()
    ZonesJoin.objects.all().delete()
    VendorDnsAccount.objects.all().delete()
    DnsAccount.objects.all().delete()
    AccountsJoin.objects.all().delete()
    Domain.objects.all().delete()
