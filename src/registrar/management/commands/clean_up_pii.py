from django.core.management import BaseCommand
from django.apps import apps
from faker import Faker
from registrar.management.commands.utility.terminal_helper import TerminalHelper
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
fake = Faker()

PII_FIELDS = {
    "Contact": ["email", "first_name", "last_name", "phone"],
    "User": ["email", "first_name", "last_name"],
    "PublicContact": ["email", "first_name", "last_name", "phone"],
    "DomainInvitation": ["email"],
    "PortfolioInvitation": ["email"],
}

SKIP_EMAIL_DOMAINS = ["ecstech.com", "cisa.dhs.gov", "truss.works", "gwe.cisa.dhs.gov", "igorville.gov"]


class Command(BaseCommand):
    help = "Clean tables in database to prepare for import."

    def handle(self, **options):
        """Clean up all pii from rows from a list of tables"""

        if settings.IS_PRODUCTION:
            logger.error("clean_pii cannot be run in production")
            return

        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message="""
            This script will delete PII from the following tables
             * Contact
             * User
             * PublicContact
             * DomainInvitation
             * PortfolioInvitation
            """,
            prompt_title="Do you wish to proceed with these changes?",
        )

        for model_name, fields in PII_FIELDS.items():
            self.scrub_pii(model_name, fields)

    def scrub_pii(self, model_name, fields):
        try:
            model = apps.get_model("registrar", model_name)
            BATCH_SIZE = 1000
            offset = 0
            updated_total = 0

            while True:
                instances = list(model.objects.all()[offset : offset + BATCH_SIZE])
                if not instances:
                    break

                for instance in instances:
                    skip_row = False
                    for field in fields:
                        if field == "email" and hasattr(instance, field):
                            current_value = getattr(instance, field)
                            if current_value:
                                for domain in SKIP_EMAIL_DOMAINS:
                                    if current_value.lower().endswith(f"@{domain}"):
                                        skip_row = True
                                        break
                        if skip_row:
                            break
                    if skip_row:
                        continue

                    for field in fields:
                        if hasattr(instance, field):
                            fake_value = self.generate_fake_value(field)
                            setattr(instance, field, fake_value)
                            instance.save()
                            updated_total += 1

                offset += BATCH_SIZE

                logger.info(f"Scrubbed {updated_total} rows in {model_name}")
        except Exception:
            logger.error(f"Model {model_name} not found")

    def generate_fake_value(self, field):
        "Return fake data based on the field type"
        if "email" in field:
            return fake.email()
        elif "first_name" in field:
            return fake.first_name()
        elif "last_name" in field:
            return fake.last_name()
        elif "phone" in field:
            return fake.phone_number()
