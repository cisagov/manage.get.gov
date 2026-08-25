"""Backfill the Domain created_at reference columns (created_at_reference, x_registry_created_at).

Script fills them from existing data and the audit log, and writes with bulk_update so updated_at is left untouched.
Verification checks that created_at_reference matches the request's original (earliest) approval date.

Usage:
    ./manage.py populate_domain_created_at_columns             # run the backfill
    ./manage.py populate_domain_created_at_columns --dry-run   # preview only, save nothing
    ./manage.py populate_domain_created_at_columns --limit 100 # preview/print this many (default 50)
    ./manage.py populate_domain_created_at_columns --debug     # print every updated domain
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

    # Default for --limit: how many records a dry run previews / a live run prints.
    DEFAULT_LIMIT = 50

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug = False
        self.dry_run = False
        self.limit = self.DEFAULT_LIMIT
        self.domain_content_type = None
        self.request_content_type = None
        self.created_at_logs = {}
        self.approval_logs = {}
        self.preview_rows = []
        self.approval_mismatches = []
        self.verify_errors = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--debug",
            action=argparse.BooleanOptionalAction,
            help="Print every updated domain (a normal run prints the first --limit).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the changes without saving.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=self.DEFAULT_LIMIT,
            help=f"How many records a dry run previews and a live run prints (default {self.DEFAULT_LIMIT}).",
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
        self.limit = kwargs.get("limit") or self.DEFAULT_LIMIT
        self.domain_content_type = ContentType.objects.get_for_model(Domain)
        self.request_content_type = ContentType.objects.get_for_model(DomainRequest)

        records = self.get_records()
        if self.dry_run:
            records = records[: self.limit]

        # count() rather than len() so we do not load every row just to show the prompt total.
        total = records.count()
        mode = "DRY RUN (no changes saved)" if self.dry_run else "LIVE"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"Mode: {mode}\nDomains to update: {total}",
            prompt_title="Backfill created_at_reference and x_registry_created_at?",
        )

        # Materialize once the run is confirmed, then prefetch the audit logs the loop needs so we
        # do not hit LogEntry per domain (get_original_created_at + get_approval_datetime).
        records = list(records)
        self.created_at_logs = self.prefetch_created_at_logs(records)
        self.approval_logs = self.prefetch_approval_logs(records)

        for record in records:
            self.update_record(record)

        if self.preview_rows:
            shown = self.preview_rows if self.debug else self.preview_rows[: self.limit]
            self.print_table(("id", "domain", "created_at_reference", "x_registry_created_at"), shown)
            remaining = len(self.preview_rows) - len(shown)
            if remaining > 0:
                self.stdout.write(f"... and {remaining} more (use --debug to print all)")

        if not self.dry_run:
            ScriptDataHelper.bulk_update_fields(Domain, records, FIELDS_TO_UPDATE, quiet=True)

        self.print_summary(len(records))

    def get_records(self):
        """Domains still missing a value, split by state.

        Unknown domains never get a registry date, so filtering on x_registry_created_at alone would
        re-pick them every run; they only need created_at_reference. select_related keeps the request
        lookup in verify_record from hitting the DB per domain.
        """
        unknown_needs_backfill = Q(state=Domain.State.UNKNOWN) & Q(created_at_reference__isnull=True)
        known_needs_backfill = ~Q(state=Domain.State.UNKNOWN) & (
            Q(created_at_reference__isnull=True) | Q(x_registry_created_at__isnull=True)
        )
        return (
            Domain.objects.filter(unknown_needs_backfill | known_needs_backfill)
            .select_related("domain_info")
            .order_by("id")
        )

    def prefetch_created_at_logs(self, records):
        """Maps domain object_pk -> its earliest audit entry that changed created_at."""
        object_pks = [str(record.pk) for record in records]
        entries = (
            LogEntry.objects.filter(
                content_type=self.domain_content_type,
                object_pk__in=object_pks,
                changes__has_key="created_at",
            )
            .only("object_pk", "timestamp", "changes")
            .order_by("object_pk", "timestamp")
        )
        logs = {}
        for entry in entries:
            # Ordered oldest first, so the first entry per domain is the earliest.
            logs.setdefault(entry.object_pk, entry)
        return logs

    def prefetch_approval_logs(self, records):
        """Maps request object_pk -> its earliest audit entry that set status to approved."""
        request_pks = {str(rid) for rid in (self.get_request_id(record) for record in records) if rid}
        entries = (
            LogEntry.objects.filter(
                content_type=self.request_content_type,
                object_pk__in=request_pks,
                # auditlog stores each change as [old, new]; __1 is the new value, so this matches
                # entries whose status changed *to* approved (e.g. {"status": ["in review", "approved"]}).
                # Same JSON index pattern is used in restore_approved_requests.py.
                changes__status__1=DomainRequest.DomainRequestStatus.APPROVED,
            )
            .only("object_pk", "timestamp")
            .order_by("object_pk", "timestamp")
        )
        logs = {}
        for entry in entries:
            logs.setdefault(entry.object_pk, entry)
        return logs

    def get_request_id(self, record: Domain):
        """The domain's request id, or None. domain_info is select_related, so no extra query."""
        try:
            return record.domain_info.domain_request_id
        except ObjectDoesNotExist:
            return None

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
        entry = self.created_at_logs.get(str(record.pk))
        change = (entry.changes_dict or {}).get("created_at") if entry else None
        if not change:
            return None
        old_value, new_value = change[0], change[1]
        # On a create the old value is "None"; the original date is the new value instead.
        candidate = old_value if old_value not in (None, "None", "") else new_value
        return self.parse_audit_datetime(candidate)

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
            self.verify_errors.append((record, err))

    def get_approval_datetime(self, record: Domain):
        """Returns the original approval time of the domain's request, or None.

        Uses the earliest approval: the record is created at the first approval, so a later
        re-approval (e.g. a restored request) is not what created_at_reference should match.
        """
        request_id = self.get_request_id(record)
        if not request_id:
            return None
        entry = self.approval_logs.get(str(request_id))
        return entry.timestamp if entry else None

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
        """Prints the run total, any approval-date mismatches, and any records that could not verify."""
        verb = "Would update" if self.dry_run else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {count} domains."))

        if self.approval_mismatches:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(self.approval_mismatches)} domains: created_at_reference does not match the approval date:"
                )
            )
            rows = [
                (record.id, record.name, reference, approval)
                for record, reference, approval in self.approval_mismatches
            ]
            self.print_table(("id", "domain", "created_at_reference", "approval"), rows)

        if self.verify_errors:
            self.stdout.write(self.style.WARNING(f"{len(self.verify_errors)} domains could not be verified:"))
            for record, err in self.verify_errors:
                self.stdout.write(self.style.WARNING(f"  {record.name}: {err}"))

        if not self.approval_mismatches and not self.verify_errors:
            self.stdout.write(self.style.SUCCESS("Verification passed: no discrepancies found."))
