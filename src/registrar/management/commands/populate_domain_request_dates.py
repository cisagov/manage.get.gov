import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import DomainRequest
from auditlog.models import LogEntry

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each domain request object and populates the last_status_update and first_submitted_date"

    def handle(self, **kwargs):
        """Loops through each DomainRequest object and populates
        its last_status_update and first_submitted_date values"""
        self.mass_update_records(DomainRequest, None, ["last_status_update", "first_submitted_date"])

    def update_record(self, record: DomainRequest):
        """Defines how we update the first_submitted_date and last_status_update fields"""

        # Retrieve and order audit log entries by timestamp in descending order
        audit_log_entries = LogEntry.objects.filter(object_pk=record.pk).order_by("-timestamp")
        # Loop through logs in descending order to find most recent status change
        for log_entry in audit_log_entries:
            if "status" in log_entry.changes_dict:
                record.last_status_update = log_entry.timestamp.date()
                break

        # Loop through logs in ascending order to find first submission
        for log_entry in audit_log_entries.reverse():
            status = log_entry.changes_dict.get("status")
            if status and status[1] == "submitted":
                record.first_submitted_date = log_entry.timestamp.date()
                break

        logger.info(f"""{TerminalColors.OKCYAN}Updating {record} =>
                first submitted date: {record.first_submitted_date},
                last status update: {record.last_status_update}{TerminalColors.ENDC}
            """)

    def should_skip_record(self, record) -> bool:
        # make sure the record had some kind of history
        return not LogEntry.objects.filter(object_pk=record.pk).exists()
