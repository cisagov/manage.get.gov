from django.core.management import BaseCommand
from django.apps import apps
from django.db import transaction
from faker import Faker
from registrar.management.commands.utility.terminal_helper import TerminalColors
from django.conf import settings
import logging
import argparse

logger = logging.getLogger(__name__)
fake = Faker()

PII_FIELDS = {
    "Contact": ["email", "first_name", "last_name", "phone"],
    "User": ["email", "first_name", "last_name"],
    "PublicContact": ["email", "first_name", "last_name", "phone", "voice"],
    "DomainInvitation": ["email"],
    "SeniorOfficial": ["email", "first_name", "last_name"],
}

SKIP_EMAIL_DOMAINS = [
    "ecstech.com",
    "cisa.dhs.gov",
    "truss.works",
    "gwe.cisa.dhs.gov",
    "igorville.gov",
    "contractors.truss.works",
    "gsa.gov",
    "example.com",
]

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Clean tables with pii in order to use as a test data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            help="Show what would be changed without making any database modifications.",
        )
        return super().add_arguments(parser)

    def handle(self, *args, **options):
        """Clean up all pii from rows from a list of tables"""

        dry_run = options.get("dry_run", False)
        if settings.IS_PRODUCTION:
            logger.error("clean_up_pii cannot be run in production")
            return

        for model_name, fields in PII_FIELDS.items():
            self.scrub_pii(model_name, fields, dry_run)

    def scrub_pii(self, model_name, fields, dry_run):
        try:
            model = apps.get_model("registrar", model_name)
        except LookupError:
            logger.error(f"{model_name} not found")
            return

        updated_total = 0
        qs = model.objects.all().iterator(chunk_size=BATCH_SIZE)

        with transaction.atomic():
            for instance in qs:
                if not instance:
                    continue
                if self.should_skip(instance):
                    continue

                new_dict = self.generate_fake_value(fields)
                updated_total += self.iterate_through_fields(fields, instance, dry_run, new_dict)

        status_text = "Would scrub" if dry_run else "Scrubbed"
        logger.info(f"_{TerminalColors.OKGREEN} {status_text} {updated_total} records in {model_name}")

    def iterate_through_fields(self, fields, instance, dry_run, new_dict):
        """Apply per-instance changes to fields with pii"""
        # Keep only fields that exist on the model
        update_fields = {f: new_dict[f] for f in fields if hasattr(instance, f)}
        if not update_fields:
            return 0

        if dry_run:
            return 1

        # Direct UPDATE to avoid save() and signals
        type(instance).objects.filter(pk=instance.pk).update(**update_fields)
        return 1

    def should_skip(self, instance):
        "Skip emails that reference current admins and data that was already scrubbed"
        email = getattr(instance, "email", None)
        if not email:
            return False
        return any(email.lower().endswith(f"@{domain}") for domain in SKIP_EMAIL_DOMAINS)

    def generate_fake_value(self, fields):
        "Return fake data dict, created a dict so that the first name and last name matches with email"
        dict = {}
        first_name = fake.first_name()
        last_name = fake.last_name()
        for field in fields:
            if "email" in field:
                dict["email"] = f"{first_name}.{last_name}@example.com"
            elif "first_name" in field:
                dict["first_name"] = first_name
            elif "last_name" in field:
                dict["last_name"] = last_name
            elif "phone" in field:
                dict["phone"] = fake.phone_number()
            elif "voice" in field:
                dict["voice"] = fake.phone_number()
        return dict
