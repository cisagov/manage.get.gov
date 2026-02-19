import logging

from django.core.management.base import BaseCommand
from auditlog.context import disable_auditlog
from registrar.fixtures.fixtures_dnsrecord import DnsRecordFixture
from registrar.fixtures.fixtures_domains import DomainFixture
from registrar.fixtures.fixtures_portfolios import PortfolioFixture
from registrar.fixtures.fixtures_requests import DomainRequestFixture
from registrar.fixtures.fixtures_suborganizations import SuborganizationFixture
from registrar.fixtures.fixtures_user_portfolio_permissions import UserPortfolioPermissionFixture
from registrar.fixtures.fixtures_users import UserFixture  # type: ignore

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        # django-auditlog has some bugs with fixtures
        # https://github.com/jazzband/django-auditlog/issues/17
        with disable_auditlog():
            UserFixture.load()
            PortfolioFixture.load()
            SuborganizationFixture.load()
            DomainRequestFixture.load()
            DomainFixture.load()
            UserPortfolioPermissionFixture.load()
            DnsRecordFixture.load()
            logger.info("All fixtures loaded.")
