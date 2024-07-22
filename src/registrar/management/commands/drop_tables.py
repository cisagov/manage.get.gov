import logging
from django.conf import settings
from django.core.management import BaseCommand
from django.apps import apps
from django.db import connection, transaction

from registrar.management.commands.utility.terminal_helper import TerminalHelper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Drops all tables in the database'

    def handle(self, **options):
        """Delete all rows from a list of tables"""

        if settings.IS_PRODUCTION:
            logger.error("drop_tables cannot be run in production")
            return

        logger.info(self.style.WARNING('Dropping all tables...'))
        with connection.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            table_names = cursor.fetchall()
            if table_names:
                try:
                    logger.info(self.style.NOTICE('Dropping tables in the database:'))
                    for name in table_names:
                        name_as_str = name[0]
                        logger.info(f"Dropping {name_as_str}")
                        cursor.execute(f"DROP TABLE {name_as_str} CASCADE;")
                except Exception as err:
                    logger.error(f"Could not drop tables from DB: {err}")
                else:
                    logger.info(self.style.SUCCESS('All tables dropped.'))
            else:
                logger.info(self.style.WARNING('No tables found.'))
