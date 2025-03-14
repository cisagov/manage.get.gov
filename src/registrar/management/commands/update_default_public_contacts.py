import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalHelper
from registrar.models import PublicContact, Domain
from django.db.models import Q

from registrar.utility.enums import DefaultEmail

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each default PublicContact and updates some values on each"

    def handle(self, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""
        old_emails = [email for email in DefaultEmail if email != DefaultEmail.PUBLIC_CONTACT_DEFAULT]
        filter_condition = {"email__in": old_emails}
        fields_to_update = [
            "name",
            "street1",
            "pc",
            "email"
        ]
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
