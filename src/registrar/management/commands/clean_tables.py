import logging
from django.conf import settings
from django.core.management import BaseCommand
from django.apps import apps
from django.db import transaction

from registrar.management.commands.utility.terminal_helper import TerminalHelper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Clean tables in database to prepare for import."

    def handle(self, **options):
        """Delete all rows from a list of tables"""

        if settings.IS_PRODUCTION:
            logger.error("clean_tables cannot be run in production")
            return

        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect="""
            This script will delete all rows from the following tables:
             * Contact
             * Domain
             * DomainInformation
             * DomainRequest
             * DraftDomain
             * FederalAgency
             * Host
             * HostIp
             * PublicContact
             * User
             * Website
            """,
            prompt_title="Do you wish to proceed with these changes?",
        )

        table_names = [
            "DomainInformation",
            "DomainRequest",
            "FederalAgency",
            "PublicContact",
            "HostIp",
            "Host",
            "Domain",
            "User",
            "Contact",
            "Website",
            "DraftDomain",
        ]

        for table_name in table_names:
            self.clean_table(table_name)

    def clean_table(self, table_name):
        """Delete all rows in the given table.

        Delete in batches to be able to handle large tables"""
        try:
            # Get the model class dynamically
            model = apps.get_model("registrar", table_name)
            BATCH_SIZE = 1000
            total_deleted = 0

            # Get initial batch of primary keys
            pks = list(model.objects.values_list("pk", flat=True)[:BATCH_SIZE])

            while pks:
                # Use a transaction to ensure database integrity
                with transaction.atomic():
                    deleted, _ = model.objects.filter(pk__in=pks).delete()
                    total_deleted += deleted
                logger.debug(f"Deleted {deleted} {table_name}s, total deleted: {total_deleted}")
                # Get the next batch of primary keys
                pks = list(model.objects.values_list("pk", flat=True)[:BATCH_SIZE])
            logger.info(f"Successfully cleaned table {table_name}, deleted {total_deleted} rows")
        except LookupError:
            logger.error(f"Model for table {table_name} not found.")
        except Exception as e:
            logger.error(f"Error cleaning table {table_name}: {e}")
