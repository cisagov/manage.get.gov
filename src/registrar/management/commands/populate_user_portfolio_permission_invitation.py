import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors, TerminalHelper
from registrar.models import UserPortfolioPermission, PortfolioInvitation
from auditlog.models import LogEntry

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each UserPortfolioPermission object and populates the invitation field"

    def handle(self, **kwargs):
        """Loops through each DomainRequest object and populates
        its last_status_update and first_submitted_date values"""
        self.existing_invitations = PortfolioInvitation.objects.filter(
            portfolio__isnull=False, email__isnull=False
        ).select_related("portfolio")
        filter_condition = {"invitation__isnull": True, "portfolio__isnull": False, "user__email__isnull": False}
        self.mass_update_records(UserPortfolioPermission, filter_condition, fields_to_update=["invitation"])

    def update_record(self, record: UserPortfolioPermission):
        """Associate the invitation to the right object"""
        record.invitation = self.existing_invitations.filter(
            email=record.user.email, portfolio=record.portfolio
        ).first()
        TerminalHelper.colorful_logger("INFO", "OKCYAN", f"{TerminalColors.OKCYAN}Adding invitation to {record}")

    def should_skip_record(self, record) -> bool:
        """There is nothing to add if no invitation exists"""
        return (
            not record
            or not self.existing_invitations.filter(email=record.user.email, portfolio=record.portfolio).exists()
        )
