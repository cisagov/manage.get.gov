from registrar.models import (
    Domain,
    DnsAccount,
    VendorDnsAccount,
    DnsVendor,
    DnsZone,
    VendorDnsZone,
    DnsRecord,
    VendorDnsRecord,
)
def make_domain(**kwargs):
    """Generate a domain object"""
    domain_name = kwargs.get("domain_name", "example.gov")
    domain = Domain.objects.create(name=domain_name)
    return domain

def make_dns_account(domain, **kwargs):
    """Generate a DNS account object and its vendor link"""
    vendor_name = DnsVendor.CF
    vendor = DnsVendor.objects.get(name=vendor_name)
    x_account_id = kwargs.get("x_account_id", "example_x_account_id")
    dns_account = DnsAccount.objects.create(name=domain.name)

    vendor_dns_account = VendorDnsAccount.objects.create(
        dns_vendor=vendor,
        x_account_id=x_account_id,
        x_created_at="2025-01-01T00:00:00Z",
        x_updated_at="2025-01-01T00:00:00Z",
    )

    dns_account.vendor_dns_account.add(vendor_dns_account)

    return dns_account

def make_zone(domain, account, **kwargs):
    """Generate a zone object and its vendor link"""
    zone_name = kwargs.get("zone_name", domain.name)
    x_zone_id = kwargs.get("x_zone_id", "example_x_zone_id")
    nameservers = kwargs.get("nameservers", ["ex1.dns.gov", "ex2.dns.gov"])
    x_created_at = kwargs.get("x_created_at", "2025-01-01T00:00:00Z")
    x_updated_at = kwargs.get("x_updated_at", "2025-01-01T00:00:00Z")
    dns_zone = DnsZone.objects.create(
        domain=domain,
        dns_account=account,
        name=zone_name,
        nameservers=nameservers,
    )

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
    dns_zone = make_zone(
        domain=domain,
        account=dns_account, **kwargs)

    return domain, dns_account, dns_zone


def make_dns_record(zone, **kwargs):
    """Generate a DNS record object and its vendor link"""
    record_name = kwargs.get("record_name", "www")
    record_type = kwargs.get("record_type", "A")
    record_content = kwargs.get("record_content", "192.168.1.1")
    x_record_id = kwargs.get("x_record_id", "example_x_record_id")
    x_created_at = kwargs.get("x_created_at", "2025-01-01T00:00:00Z")
    x_updated_at = kwargs.get("x_updated_at", "2025-01-01T00:00:00Z")
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