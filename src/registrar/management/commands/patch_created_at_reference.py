# src/registrar/management/commands/patch_created_at_from_reference.py

import argparse
import logging

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import F

from registrar.models import Domain

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Copies values from created_at_reference into created_at so the two columns match"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "When enabled (which is the default), does NOT write to the db, only shows what would be updated. "
                "Disable with --no-dry-run to perform the import."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help=f"Number of rows to update per batch (default: {BATCH_SIZE}).",
        )

    def handle(self, *args, **options):
        """
        How to run:
            ./manage.py patch_created_at_reference (dry run is ON by default)
            ./manage.py patch_created_at_reference --no-dry-run
            ./manage.py patch_created_at_from_reference --no-dry-run --batch-size 10000
        """
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        warnings = self.get_warnings()
        mismatched_qs, total_mismatched = self.get_mismatched_queryset()

        if total_mismatched == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "Nothing to do. created_at already matches created_at_reference for all eligible rows."
                )
            )
            self.print_warnings(warnings)
            return

        self.stdout.write(
            f"Found {total_mismatched} row(s) where created_at != created_at_reference (excluding NULL references)."
        )

        if dry_run:
            self.run_dry_run(mismatched_qs, total_mismatched, warnings)
            return

        total_updated, errors = self.run_live_update(mismatched_qs, batch_size, total_mismatched)
        self.print_summary(total_updated, total_mismatched, warnings, errors)

    def get_warnings(self):
        """Rows where created_at_reference is NULL are skipped entirely - copying NULL into
        created_at would erase an existing timestamp and we don't want that"""
        null_reference_count = Domain.objects.filter(created_at_reference__isnull=True).count()
        if not null_reference_count:
            return []
        return [
            f"{null_reference_count} row(s) have a NULL created_at_reference and will be skipped. "
            "Their created_at will be left untouched."
        ]

    def get_mismatched_queryset(self):
        """
        Only rows where the two columns differ (+ exclude NULL) need writing -
        avoids no op UPDATEs on rows already correct
        """
        mismatched_qs = Domain.objects.exclude(created_at=F("created_at_reference")).exclude(
            created_at_reference__isnull=True
        )
        return mismatched_qs, mismatched_qs.count()

    def run_dry_run(self, mismatched_qs, total_mismatched, warnings):
        """
        Prints a preview (not the full set, on purpose) of the first 10 mismatched rows
        """
        self.stdout.write(self.style.WARNING("Dry run ON (default) — no changes will be written."))
        self.stdout.write("Sample of rows that would be updated:")
        for domain in mismatched_qs.only("id", "created_at", "created_at_reference")[:10]:
            self.stdout.write(f"  id={domain.id}  created_at={domain.created_at} -> {domain.created_at_reference}")
        if total_mismatched > 10:
            self.stdout.write(f"  ... and {total_mismatched - 10} more row(s).")
        self.print_warnings(warnings)
        self.stdout.write(self.style.WARNING(f"Dry run complete. {total_mismatched} row(s) would be updated."))

    def run_live_update(self, mismatched_qs, batch_size, total_mismatched):
        """
        Batches through pks so we're not holding one giant lock, and so a failure
        partway through doesn't lose all prior progress

        flat=True grabs just the ids into a list ie [1, 2, 3] instead of [(1,), (2,), (3,)]
        list() runs the query once so it's stored and not requeried on every slice
        """
        pk_list = list(mismatched_qs.order_by("pk").values_list("pk", flat=True))

        total_updated = 0
        errors = []

        for start in range(0, len(pk_list), batch_size):
            batch_pks = pk_list[start : start + batch_size]
            updated_count, error = self.update_batch(batch_pks, start)
            if error:
                errors.append(error)
                continue
            total_updated += updated_count
            self.stdout.write(
                self.style.SUCCESS(
                    f"Batch {start // batch_size + 1}: updated {updated_count} row(s). "
                    f"Running total: {total_updated}/{total_mismatched}"
                )
            )

        return total_updated, errors

    def update_batch(self, batch_pks, start):
        """
        Updates a single batch inside its own transaction, so one failed batch
        can't break the ones before or after it

        Returns (updated_count, error_msg_or_None)
        """
        try:
            with transaction.atomic():
                updated_count = Domain.objects.filter(pk__in=batch_pks).update(created_at=F("created_at_reference"))
            return updated_count, None
        except Exception as e:
            error_msg = self.build_batch_error_message(batch_pks, start, e)
            logger.error(error_msg)
            self.stdout.write(self.style.ERROR(error_msg))
            return 0, error_msg

    def build_batch_error_message(self, batch_pks, start, exception):
        """
        Grabs domain name + id for the failed batchs rows so the error is readable
        """
        failed_domains = list(Domain.objects.filter(pk__in=batch_pks).values_list("id", "name"))
        return (
            f"Batch starting at offset {start} (pks {batch_pks[0]}-{batch_pks[-1]}) failed: {exception}\n"
            f"  Affected domains ({len(failed_domains)}): "
            + ", ".join(f"{name} (id={pk})" for pk, name in failed_domains[:20])
            + (f" ... and {len(failed_domains) - 20} more" if len(failed_domains) > 20 else "")
        )

    def print_warnings(self, warnings):
        for w in warnings:
            self.stdout.write(self.style.WARNING(w))

    def print_summary(self, total_updated, total_mismatched, warnings, errors):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Done. {total_updated}/{total_mismatched} row(s) updated."))

        if warnings:
            self.stdout.write(self.style.WARNING(f"{len(warnings)} warning(s):"))
            self.print_warnings([f"  - {w}" for w in warnings])

        if errors:
            self.stdout.write(self.style.ERROR(f"{len(errors)} error(s) occurred - see above / logs for details."))
            logger.error("patch_created_at_reference finished with %s error(s)", len(errors))
        else:
            logger.info("patch_created_at_reference: updated %s rows successfully", total_updated)
