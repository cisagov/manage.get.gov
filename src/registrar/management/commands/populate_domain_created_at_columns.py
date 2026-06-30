"""Backfill the Domain created_at reference columns (created_at_reference, x_registry_created_at).

Script fills them from existing data and the audit log, and writes with bulk_update so updated_at is left untouched.
Verification checks that created_at_reference matches the request's original (earliest) approval date.

Usage:
    ./manage.py populate_domain_created_at_columns            # run the backfill
    ./manage.py populate_domain_created_at_columns --dry-run  # preview up to 50, save nothing
    ./manage.py populate_domain_created_at_columns --debug    # also print each domain as it updates
"""

import argparse
from datetime import timezone as dt_timezone
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from auditlog.models import LogEntry
from registrar.management.commands.utility.terminal_helper import ScriptDataHelper, TerminalHelper
from registrar.models import Domain, DomainRequest

FIELDS_TO_UPDATE = ["created_at_reference", "x_registry_created_at"]


class Command(BaseCommand):
    help = "Backfills Domain created_at_reference and x_registry_created_at from existing data and the audit log."

    # Dry runs preview this many records so a full table doesn't flood the output.
    DRY_RUN_LIMIT = 50

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug = False
        self.dry_run = False
        self.domain_content_type = None
        self.request_content_type = None
        self.preview_rows = []
        self.approval_mismatches = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--debug",
            action=argparse.BooleanOptionalAction,
            help=f"Print every updated domain (a normal run shows the first {self.DRY_RUN_LIMIT}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=f"Preview up to {self.DRY_RUN_LIMIT} records without saving.",
        )

    def handle(self, **kwargs):
        """Backfills both columns.

        created_at_reference: when the record was created in the registrar (from the audit log).
        x_registry_created_at: when the domain was created in the registry; for non-unknown domains
            created_at already holds that value, so it is copied across.

        Writes with bulk_update, so updated_at (auto_now) is left untouched.
        """
        self.debug = kwargs.get("debug")
        self.dry_run = kwargs.get("dry_run", False)
        self.domain_content_type = ContentType.objects.get_for_model(Domain)
        self.request_content_type = ContentType.objects.get_for_model(DomainRequest)

        records = self.get_records()
        if self.dry_run:
            records = list(records[: self.DRY_RUN_LIMIT])
        total = len(records)

        mode = "DRY RUN (no changes saved)" if self.dry_run else "LIVE"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"Mode: {mode}\nDomains to update: {total}",
            prompt_title="Backfill created_at_reference and x_registry_created_at?",
        )

        to_update = []
        for record in records:
            self.update_record(record)
            to_update.append(record)

        if self.preview_rows:
            shown = self.preview_rows if self.debug else self.preview_rows[: self.DRY_RUN_LIMIT]
            self.print_table(("id", "domain", "created_at_reference", "x_registry_created_at"), shown)
            remaining = len(self.preview_rows) - len(shown)
            if remaining > 0:
                self.stdout.write(f"... and {remaining} more (use --debug to print all)")

        if not self.dry_run:
            ScriptDataHelper.bulk_update_fields(Domain, to_update, FIELDS_TO_UPDATE, quiet=True)

        self.print_summary(len(to_update))

    def get_records(self):
        """Domains still missing a value, split by state.

        Unknown domains never get a registry date, so filtering on x_registry_created_at alone would
        re-pick them every run; they only need created_at_reference.
        """
        unknown_needs_backfill = Q(state=Domain.State.UNKNOWN) & Q(created_at_reference__isnull=True)
        known_needs_backfill = ~Q(state=Domain.State.UNKNOWN) & (
            Q(created_at_reference__isnull=True) | Q(x_registry_created_at__isnull=True)
        )
        return Domain.objects.filter(unknown_needs_backfill | known_needs_backfill).order_by("id")

    def update_record(self, record: Domain):
        """Sets both columns on the in-memory record.

        Unknown domains keep their registrar created_at and have no registry date. For other states
        created_at holds the registry date, so it copies into x_registry_created_at while the original
        registrar date is recovered from the audit log.
        """
        if record.state == Domain.State.UNKNOWN:
            record.created_at_reference = record.created_at
        else:
            record.created_at_reference = self.get_original_created_at(record) or record.created_at
            record.x_registry_created_at = record.created_at

        self.verify_record(record)
        self.preview_rows.append(
            (
                record.id,
                record.name,
                record.created_at_reference or "",
                record.x_registry_created_at or "",
            )
        )

    def get_original_created_at(self, record: Domain):
        """Returns the earliest created_at value recorded for this domain in the audit log.

        That first recorded value is the registrar record-creation date, before created_at was
        overwritten with the registry date.
        """
        entries = LogEntry.objects.filter(content_type=self.domain_content_type, object_pk=str(record.pk)).order_by(
            "timestamp"
        )
        for entry in entries:
            change = (entry.changes_dict or {}).get("created_at")
            if change:
                old_value, new_value = change[0], change[1]
                # On a create the old value is "None"; the original date is the new value instead.
                candidate = old_value if old_value not in (None, "None", "") else new_value
                return self.parse_audit_datetime(candidate)
        return None

    def parse_audit_datetime(self, value):
        """Parses an audit-log datetime string into an aware datetime.

        Auditlog stores datetimes as naive UTC strings, so reattach UTC after parsing.
        """
        if value in (None, "None", ""):
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            return None
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, dt_timezone.utc)
        return parsed

    def verify_record(self, record: Domain):
        """Collects a finding when created_at_reference (our record-creation date) does not match the
        request approval date - the record is created at approval, so they should line up. Findings
        are reported at the end and never block the update."""
        try:
            if record.created_at_reference:
                approval = self.get_approval_datetime(record)
                if approval and approval.date() != record.created_at_reference.date():
                    self.approval_mismatches.append((record, record.created_at_reference, approval))
        except Exception as err:
            self.stderr.write(self.style.WARNING(f"Could not verify {record.name}: {err}"))

    def get_approval_datetime(self, record: Domain):
        """Returns the original approval time of the domain's request, or None.

        Uses the earliest approval: the record is created at the first approval, so a later
        re-approval (e.g. a restored request) is not what created_at_reference should match.
        """
        try:
            request_id = record.domain_info.domain_request_id
        except ObjectDoesNotExist:
            return None
        if not request_id:
            return None
        approval_log = (
            LogEntry.objects.filter(
                content_type=self.request_content_type,
                object_pk=str(request_id),
                changes__status__1=DomainRequest.DomainRequestStatus.APPROVED,
            )
            .order_by("timestamp")
            .first()
        )
        return approval_log.timestamp if approval_log else None

    def print_table(self, headers, rows):
        """Prints rows as a fixed-width column table (header, separator, then rows)."""
        widths = [max(len(str(cell)) for cell in column) for column in zip(*([headers] + rows))]

        def as_row(cells):
            return "  ".join(str(cell).ljust(width) for cell, width in zip(cells, widths))

        self.stdout.write(as_row(headers))
        self.stdout.write(as_row(tuple("-" * width for width in widths)))
        for row in rows:
            self.stdout.write(as_row(row))

    def print_summary(self, count):
        """Prints the run total and any approval-date mismatches."""
        verb = "Would update" if self.dry_run else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {count} domains."))

        if not self.approval_mismatches:
            self.stdout.write(self.style.SUCCESS("Verification passed: no approval-date discrepancies."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"{len(self.approval_mismatches)} domains: created_at_reference does not match the approval date:"
            )
        )
        rows = [
            (record.id, record.name, reference, approval) for record, reference, approval in self.approval_mismatches
        ]
        self.print_table(("id", "domain", "created_at_reference", "approval"), rows)
