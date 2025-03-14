import logging
import argparse
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalHelper
from registrar.models import PublicContact, Domain
from django.db.models import Q

from registrar.models.utility.generic_helper import normalize_string
from registrar.utility.enums import DefaultEmail

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each default PublicContact and updates some values on each"

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument(
            "--overwrite_updated_contacts",
            action=argparse.BooleanOptionalAction,
            help=(
                "Loops over PublicContacts with the email 'help@get.gov' when enabled."
                "Use this setting if the record was updated in the DB but not correctly in EPP."
            ),
        )

    def handle(self, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""
        overwrite_updated_contacts = kwargs.get("overwrite_updated_contacts")
        default_emails = {email for email in DefaultEmail}

        # Don't update records we've already updated
        if not overwrite_updated_contacts:
            default_emails.remove(DefaultEmail.PUBLIC_CONTACT_DEFAULT)

        # We should only update DEFAULT records. This means that if all values are not default,
        # we should skip as this could lead to data corruption.
        # Since we check for all fields, we don't account for casing differences.
        self.old_and_new_default_contact_values = {
            "name": {
                "csd/cb – attn: .gov tld",
                "csd/cb – attn: cameron dixon",
                "program manager",
                "registry customer service",
            },
            "street1": {"1110 n. glebe rd", "cisa – ngr stop 0645", "4200 wilson blvd."},
            "pc": {"22201", "20598-0645"},
            "email": default_emails,
        }

        filter_condition = {"email__in": default_emails}
        self.mass_update_records(PublicContact, filter_condition, [], skip_bulk_update=True)

    def update_record(self, record: PublicContact):
        """Defines how we update the verification_type field"""
        record.name = "CSD/CB – Attn: .gov TLD"
        record.street1 = "1110 N. Glebe Rd"
        record.pc = "22201"
        record.email = DefaultEmail.PUBLIC_CONTACT_DEFAULT
        TerminalHelper.colorful_logger("INFO", "OKCYAN", f"Updating default values for '{record}'.")
        record.save()
        TerminalHelper.colorful_logger("INFO", "OKCYAN", f"Updated record in EPP.")

    def should_skip_record(self, record) -> bool:  # noqa
        """Skips updating a public contact if it contains different default info."""
        for key, expected_values in self.old_and_new_default_contact_values.items():
            record_field = normalize_string(getattr(record, key))
            if record_field not in expected_values:
                message = (
                    f"Skipping '{record}' to avoid data corruption. "
                    f"The field '{key}' does not match the default.\n"
                    f"Details: DB value - {record_field}, expected value(s) - {expected_values}"
                )
                TerminalHelper.colorful_logger("WARNING", "YELLOW", message)
                return False
        return True
