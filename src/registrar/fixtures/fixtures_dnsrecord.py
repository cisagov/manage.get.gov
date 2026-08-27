import logging
from faker import Faker

from django.conf import settings
from registrar.fixtures.fixtures_domains import DomainFixture
from registrar.models import Domain
from registrar.utility.enums import DNSRecordTypes
from registrar.tests.helpers.dns_data_generator import create_dns_record

fake = Faker()
logger = logging.getLogger(__name__)


class DnsRecordFixture(DomainFixture):
    """Create DNS zones and DNS records for existing domains.

    Depends on fixtures_domains.
    """

    @classmethod
    def load(cls):
        """Create DNS zones and records for approved domains enrolled in DNS hosting."""
        if not settings.DNS_MOCK_EXTERNAL_APIS:
            logger.info(
                "Skipping DNS record fixture — DNS_MOCK_EXTERNAL_APIS is False. "
                "Enroll domains via the admin to provision real Cloudflare resources."
            )
            return

        try:
            # Get approved domains that are enrolled in DNS hosting
            domains = Domain.objects.filter(is_enrolled_in_dns_hosting=True)[:5]

            logger.info(f"Found {domains.count()} domains enrolled in DNS hosting (taking first 5)")

            if not domains:
                logger.info("No domains available. Make sure domains have is_enrolled_in_dns_hosting=True")
                return

            zones = []
            for d in domains:
                zone = d.dnszone
                zones.append(zone)

            # Create DNS records for each zone
            for dns_zone in zones:
                # Root A record
                create_dns_record(
                    dns_zone,
                    **{
                        "record_name": dns_zone.name,
                        "record_type": DNSRecordTypes.A,
                        "record_content": fake.ipv4(),
                        "x_record_id": fake.uuid4().replace("-", ""),
                    },
                )

                # A: WWW subdomain
                create_dns_record(
                    dns_zone,
                    **{
                        "record_name": "www",
                        "record_type": DNSRecordTypes.A,
                        "record_content": fake.ipv4(),
                        "x_record_id": fake.uuid4().replace("-", ""),
                        "comment": "WWW subdomain",
                    },
                )

                # A: API subdomain
                create_dns_record(
                    dns_zone,
                    **{
                        "record_name": "api",
                        "record_type": DNSRecordTypes.A,
                        "record_content": fake.ipv4(),
                        "x_record_id": fake.uuid4().replace("-", ""),
                        "comment": "api endpoint",
                    },
                )

                # AAAA
                create_dns_record(
                    dns_zone,
                    **{
                        "record_name": dns_zone.name,
                        "record_type": DNSRecordTypes.AAAA,
                        "record_content": fake.ipv6(),
                        "x_record_id": fake.uuid4().replace("-", ""),
                    },
                )

                # PTR
                create_dns_record(
                    dns_zone,
                    **{
                        "record_name": dns_zone.name,
                        "record_type": DNSRecordTypes.PTR,
                        "record_content": dns_zone.name,
                        "x_record_id": fake.uuid4().replace("-", ""),
                    },
                )

                # CNAME
                create_dns_record(
                    dns_zone,
                    **{
                        "record_name": "blog.something.gov",
                        "record_type": DNSRecordTypes.CNAME,
                        "record_content": "blog.something.com",
                        "x_record_id": fake.uuid4().replace("-", ""),
                    },
                )

                # MX: mail routing
                create_dns_record(
                    dns_zone,
                    **{
                        "record_name": dns_zone.name,
                        "record_type": DNSRecordTypes.MX,
                        "record_content": f"mail.{dns_zone.name}",
                        "x_record_id": fake.uuid4().replace("-", ""),
                        "comment": "Primary mail server",
                    },
                )

            logger.info("Successfully created DNS records.")

        except Exception as e:
            logger.error(f"Error creating DNS record fixtures: {e}")
