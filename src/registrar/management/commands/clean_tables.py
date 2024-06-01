import logging
from django.core.management import BaseCommand
from django.apps import apps
from django.db import transaction

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Clean tables in database to prepare for import."

    def handle(self, **options):
        """Delete all rows from a list of tables"""
        table_names = [
            "DomainInformation", "DomainRequest", "Domain", "User", "Contact", 
            "Website", "DraftDomain", "HostIp", "Host"
        ]
        
        for table_name in table_names:
            self.clean_table(table_name)

    def clean_table(self, table_name):
        """Delete all rows in the given table"""
        try:
            # Get the model class dynamically
            model = apps.get_model('registrar', table_name)
            # Use a transaction to ensure database integrity
            with transaction.atomic():
                model.objects.all().delete()
            logger.info(f"Successfully cleaned table {table_name}")
        except LookupError:
            logger.error(f"Model for table {table_name} not found.")
        except Exception as e:
            logger.error(f"Error cleaning table {table_name}: {e}")
