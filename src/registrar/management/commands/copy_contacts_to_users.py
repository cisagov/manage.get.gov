import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import User, Contact
from registrar.models.utility.domain_helper import DomainHelper

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each valid User object and updates its verification_type value"

    # Get the fields that exist on both User and Contact. Excludes id.
    common_fields = DomainHelper.get_common_fields(User, Contact)

    def handle(self, **kwargs):
        """Loops through each valid User object and updates its verification_type value"""

        # Don't change the email field.
        if "email" in self.common_fields:
            self.common_fields.remove("email")

        filter_condition = {"contact__isnull": False}
        self.mass_populate_field(User, filter_condition, self.common_fields)

        skipped_users = User.objects.filter(contact__isnull=True)

        if skipped_users and len(skipped_users) > 0:
            logger.warning(
                f"""{TerminalColors.YELLOW}
                ===== SKIPPED USERS =====
                {list(skipped_users)}

                {TerminalColors.ENDC}
                """,
            )

    def populate_field(self, object_to_update):
        """Defines how we update the user field on mass_populate_field()"""
        new_value = None
        for field in self.common_fields:
            # Grab the value that contact has stored for this field
            new_value = getattr(object_to_update.contact, field)

            # Set it on the user field
            setattr(object_to_update, field, new_value)

        logger.info(
            f"{TerminalColors.OKCYAN}Updating {object_to_update}{TerminalColors.ENDC}"
        )
