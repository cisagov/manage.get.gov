"""
Cloudflare/DB sync report.

Compares the CF tenant accounts against the DnsAccount rows in
this environment's database and prints one row per mismatch.
"""

import logging
from collections import Counter

from django.conf import settings
from django.core.management import BaseCommand

from registrar.models import Domain
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount
from registrar.services.dns_host_service import DnsHostService
from registrar.services.utility.dns_helper import get_dns_zone_name_from_account_name

logger = logging.getLogger(__name__)

# Mismatch types
VENDOR_ONLY = "vendor_only"
VENDOR_ONLY_WITH_ZONE = "vendor_only_with_zone"
DB_ONLY = "db_only"

MISMATCH_TYPES = (VENDOR_ONLY, VENDOR_ONLY_WITH_ZONE, DB_ONLY)

ACCOUNT = "account"

COLUMNS = ("domain", "object_type", "name", "cf_id", "db_id", "mismatch_type", "duplicate_name", "domain_in_db")


class Command(BaseCommand):
    help = (
        "Read-only report of Cloudflare accounts that are out of sync with the registrar database "
        "in the environment this command is run in. Prints one row per mismatch to stdout"
    )

    def handle(self, *args, **options):
        comparison = DnsHostService().compare_vendor_and_db_accounts()
        rows = self.build_rows(comparison)

        self.print_report(rows)

        counts = Counter(row["mismatch_type"] for row in rows)

        logger.info(
            "CF/DB sync report for %s: %s mismatches (%s); %s synced accounts",
            settings.BASE_URL,
            len(rows),
            ", ".join(f"{t}={counts.get(t, 0)}" for t in MISMATCH_TYPES),
            len(comparison["synced_accounts"]),
        )

    def build_rows(self, comparison: dict) -> list[dict]:
        """Convert the output of DnsHostService.compare_vendor_and_db_accounts into report rows."""
        db_ids_by_name = dict(
            DnsAccount_VendorDnsAccount.objects.filter(is_active=True).values_list(
                "dns_account__name", "vendor_dns_account__x_account_id"
            )
        )
        with_zone = set(comparison["vendor_accounts_with_zone_no_db"])
        duplicate_names = set(comparison["duplicate_account_names"])

        rows = []
        for name, cf_id in comparison["vendor_only"]:
            mismatch = VENDOR_ONLY_WITH_ZONE if (name, cf_id) in with_zone else VENDOR_ONLY
            rows.append(
                self._row(
                    name,
                    cf_id=cf_id,
                    db_id=db_ids_by_name.get(name, ""),
                    mismatch=mismatch,
                    duplicate=name in duplicate_names,
                )
            )
        for name, db_id in comparison["db_only"]:
            rows.append(self._row(name, cf_id="", db_id=db_id, mismatch=DB_ONLY, duplicate=name in duplicate_names))
        return rows

    def _row(self, account_name: str, cf_id: str, db_id: str, mismatch: str, duplicate: bool) -> dict:
        try:
            domain_name = get_dns_zone_name_from_account_name(account_name)
        except ValueError:
            domain_name = None

        return {
            "domain": domain_name or "",
            "object_type": ACCOUNT,
            "name": account_name,
            "cf_id": cf_id,
            "db_id": db_id,
            "mismatch_type": mismatch,
            "duplicate_name": "yes" if duplicate else "no",
            "domain_in_db": "yes" if domain_name and Domain.objects.filter(name=domain_name).exists() else "no",
        }

    def print_report(self, rows: list[dict]) -> None:
        if not rows:
            self.stdout.write("No mismatches")
            return

        widths = self._get_column_widths(rows)

        # The header line is the same for every group:
        header_cells = []
        for column in COLUMNS:
            header = column.upper()
            header_cells.append(header.ljust(widths[column]))
        header_line = "  ".join(header_cells)

        # Now group similar mismatches together and print
        for mismatch_type in MISMATCH_TYPES:
            group = []
            for row in rows:
                if row["mismatch_type"] == mismatch_type:
                    group.append(row)

            if not group:
                continue

            # Sorting should be stable, so rows with the same domain keep the order that
            # comparison gave them
            group.sort(key=lambda row: row["domain"])

            self.stdout.write("")
            self.stdout.write(f"{mismatch_type.upper()} ({len(group)})")
            self.stdout.write(header_line)

            for row in group:
                self.stdout.write(self._format_line(row, widths))

    def _get_column_widths(self, rows: list[dict]) -> dict:
        widths = {}
        for column in COLUMNS:
            widths[column] = len(column)

        for row in rows:
            for column in COLUMNS:
                value = str(row[column])
                if len(value) > widths[column]:
                    widths[column] = len(value)

        return widths

    def _format_line(self, values: dict, widths: dict) -> str:
        cells = []
        for column in COLUMNS:
            value = str(values[column])
            cells.append(value.ljust(widths[column]))

        return "  ".join(cells)
