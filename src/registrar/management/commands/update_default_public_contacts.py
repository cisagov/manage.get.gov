import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalHelper
from registrar.models import PublicContact, Domain
from django.db.models import Q

from registrar.models.utility.generic_helper import normalize_string
from registrar.utility.enums import DefaultEmail

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each default PublicContact and updates some values on each"

    def handle(self, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""

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
            "email": {email for email in DefaultEmail},
        }
        old_emails = [email for email in DefaultEmail if email != DefaultEmail.PUBLIC_CONTACT_DEFAULT]
        filter_condition = {"email__in": old_emails}
        fields_to_update = ["name", "street1", "pc", "email"]
        self.mass_update_records(PublicContact, filter_condition, fields_to_update)

    def update_record(self, record: PublicContact):
        """Defines how we update the verification_type field"""
        record.name = "CSD/CB – Attn: .gov TLD"
        record.street1 = "1110 N. Glebe Rd"
        record.pc = "22201"
        record.email = DefaultEmail.PUBLIC_CONTACT_DEFAULT
        TerminalHelper.colorful_logger("INFO", "OKCYAN", f"Updating default values for '{record}'.")
        TerminalHelper.colorful_logger("INFO", "MAGENTA", f"Attempting to update record in EPP...")
        # Since this function raises an error, this update will revert on both the model and here
        Domain._set_singleton_contact(record, expectedType=record.contact_type)
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
