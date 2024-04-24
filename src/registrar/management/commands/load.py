import logging

from django.core.management.base import BaseCommand
from auditlog.context import disable_auditlog  # type: ignore


from registrar.fixtures_users import UserFixture
from registrar.fixtures_domain_requests import DomainRequestFixture, DomainFixture

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        # django-auditlog has some bugs with fixtures
        # https://github.com/jazzband/django-auditlog/issues/17
        with disable_auditlog():
            UserFixture.load()
            DomainRequestFixture.load()
            DomainFixture.load()
            logger.info("All fixtures loaded.")
