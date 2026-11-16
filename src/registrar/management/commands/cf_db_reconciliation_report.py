"""
Cloudflare/DB reconciliation report.

Compares the CF tenant accounts against the DnsAccount rows in 
this environment's database and prints one row per mismatch. 
"""

import logging
from collections import Counter
from typing import Optional

from django.conf import settings
from django.core.management import BaseCommand

from registrar.models import Domain
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount
from registrar.services.dns_host_service import DnsHostService
from registrar.services.utility.dns_helper import get_dns_zone_name_from_account_name

logger = logging.getLogger(__name__)

# Mismatch types
DUPLICATE_NAME = "duplicate_name"
VENDOR_ONLY = "vendor_only"
VENDOR_ONLY_WITH_ZONE = "vendor_only_with_zone"
DB_ONLY = "db_only"

MISMATCH_TYPES = (DUPLICATE_NAME, VENDOR_ONLY, VENDOR_ONLY_WITH_ZONE, DB_ONLY)

ACCOUNT = "account"

COLUMNS = ("domain", "object_type", "name", "cf_id", "db_id", "mismatch_type", "domain_in_db")


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
            "CF/DB reconcilitation report for %s: %s mismatches (%s); %s synced accounts",
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

        rows = []
        for name in comparison["duplicate_account_names"]:
            rows.append(self._row(name, cf_id="", db_id=db_ids_by_name.get(name, ""), mismatch=DUPLICATE_NAME))
        for name, cf_id in comparison["vendor_only"]:
            mismatch = VENDOR_ONLY_WITH_ZONE if (name, cf_id) in with_zone else VENDOR_ONLY
            rows.append(self._row(name, cf_id=cf_id, db_id=db_ids_by_name.get(name, ""), mismatch=mismatch))
        for name, db_id in comparison["db_only"]:
            rows.append(self._row(name, cf_id="", db_id=db_id, mismatch=DB_ONLY))
        return rows

    def _row(self, account_name: str, cf_id: str, db_id: str, mismatch: str) -> dict:
        domain_name = self._domain_from_account_name(account_name)
        return {
            "domain": domain_name or "",
            "object_type": ACCOUNT,
            "name": account_name,
            "cf_id": cf_id,
            "db_id": db_id,
            "mismatch_type": mismatch,
            "domain_in_db": "yes" if domain_name and Domain.objects.filter(name=domain_name).exists else "no",
        }

    @staticmethod
    def _domain_from_account_name(account_name: str) -> Optional[str]:
        try:
            return get_dns_zone_name_from_account_name(account_name)
        except ValueError:
            return None

    def print_report(self, rows:list[dict]) -> None:
        if not rows:
            self.stdout.write("No mismatches")
            return

        widths = {col: max(len(col), *(len(str(r[col])) for r in rows)) for col in COLUMNS}
        self.stdout.write("  ".join(col.upper().ljust(widths[col]) for col in COLUMNS))
        for row in rows:
            self.stdout.write("  ".join(str(row[col]).ljust(widths[col]) for col in COLUMNS))