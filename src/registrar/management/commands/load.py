import logging

from django.core.management.base import BaseCommand
from auditlog.context import disable_auditlog  # type: ignore
from django.conf import settings

from registrar.fixtures import UserFixture, DomainApplicationFixture, DomainFixture

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        # django-auditlog has some bugs with fixtures
        # https://github.com/jazzband/django-auditlog/issues/17
        # if settings.DEBUG:
        with disable_auditlog():
            UserFixture.load()
            DomainApplicationFixture.load()
            DomainFixture.load()
            logger.info("All fixtures loaded.")
        # else:
        #     logger.warn("Refusing to load fixture data in a non DEBUG env")
