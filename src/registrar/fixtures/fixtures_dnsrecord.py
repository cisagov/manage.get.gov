import logging
from faker import Faker

from registrar.fixtures.fixtures_domains import DomainFixture
from registrar.models import Domain
from registrar.models.dns.dns_record import DnsRecord
from registrar.models.dns.dns_zone import DnsZone
from registrar.models.dns.dns_account import DnsAccount
from registrar.services.utility.dns_helper import make_dns_account_name
from registrar.utility.enums import DNSRecordTypes

fake = Faker()
logger = logging.getLogger(__name__)


class DnsRecordFixture(DomainFixture):
    """Create DNS zones and DNS records for existing domains.

    Depends on fixtures_domains.
    """

    @classmethod
    def load(cls):
        """Create DNS zones and records for approved domains enrolled in DNS hosting."""
        try:
            # Get approved domains that are enrolled in DNS hosting
            domains = Domain.objects.filter(is_enrolled_in_dns_hosting=True, dnszone__isnull=True)[:5]

            logger.info(f"Found {domains.count()} domains enrolled in DNS hosting (taking first 5)")

            if not domains:
                logger.info("No domains available. Make sure domains have is_enrolled_in_dns_hosting=True")
                return

            dns_zones_to_create = []
            dns_records_to_create = []

            for domain in domains:
                # Create or get a DNS account for this domain
                account_name = make_dns_account_name(domain.name)
                dns_account, created = DnsAccount.objects.get_or_create(name=account_name)
                if created:
                    logger.info(f"Created DNS account: {account_name}")

                # Create a DNS zone for each domain with the DNS account
                dns_zone = DnsZone(
                    domain=domain,
                    dns_account=dns_account,
                    name=domain.name,
                    nameservers=["ns1.example.gov", "ns2.example.gov"],
                )
                dns_zones_to_create.append(dns_zone)

            # Bulk create DNS zones
            created_zones = DnsZone.objects.bulk_create(dns_zones_to_create)
            logger.info(f"Successfully created {len(created_zones)} DNS zones.")

            # Create DNS records for each zone
            for dns_zone in created_zones:
                # Root A record
                dns_records_to_create.append(
                    DnsRecord(
                        dns_zone=dns_zone,
                        type=DNSRecordTypes.A,
                        name="@",
                        ttl=3600,
                        content=fake.ipv4(),
                        comment="Root domain A record",
                        tags=["production", "primary"],
                    )
                )

                # WWW subdomain A record
                dns_records_to_create.append(
                    DnsRecord(
                        dns_zone=dns_zone,
                        type=DNSRecordTypes.A,
                        name="www",
                        ttl=3600,
                        content=fake.ipv4(),
                        comment="WWW subdomain",
                        tags=["production"],
                    )
                )

                # Mail subdomain A record
                dns_records_to_create.append(
                    DnsRecord(
                        dns_zone=dns_zone,
                        type=DNSRecordTypes.A,
                        name="mail",
                        ttl=7200,
                        content=fake.ipv4(),
                        comment="Mail server",
                        tags=["email", "production"],
                    )
                )

                # API subdomain A record
                dns_records_to_create.append(
                    DnsRecord(
                        dns_zone=dns_zone,
                        type=DNSRecordTypes.A,
                        name="api",
                        ttl=1800,
                        content=fake.ipv4(),
                        comment="API endpoint",
                        tags=["production", "api"],
                    )
                )

                # Dev subdomain A record
                dns_records_to_create.append(
                    DnsRecord(
                        dns_zone=dns_zone,
                        type=DNSRecordTypes.A,
                        name="dev",
                        ttl=300,
                        content=fake.ipv4(),
                        comment="Development environment",
                        tags=["development", "non-production"],
                    )
                )

            # Bulk create DNS records
            created_records = DnsRecord.objects.bulk_create(dns_records_to_create)
            logger.info(f"Successfully created {len(created_records)} DNS records.")

        except Exception as e:
            logger.error(f"Error creating DNS record fixtures: {e}")
