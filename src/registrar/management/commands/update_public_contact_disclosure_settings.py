"""Update registry disclose settings for existing PublicContact records.

This command is intended for operational backfills against a 3rd-party registry.

Version 1 keeps the behavior intentionally narrow:
- Computes disclose via Domain._disclose_fields
- In dry-run mode (default), only logs what would be changed
- With --no-dry-run, sends registry updates via Domain._update_epp_contact

Safety rail: --target-domain is required to avoid mass updates.
"""

import argparse
import logging
from typing import Any

from django.core.management import BaseCommand

from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import PublicContact

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Updates registry disclose settings for PublicContact records to whatever the website currently computes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-domain",
            "--target_domain",
            required=True,
            help=(
                "Only update contacts for a given domain name - case insensitive. "
            ),
        )

        parser.add_argument(
            "--contact-type",
            "--contact_type",
            action="append",
            choices=[choice.value for choice in PublicContact.ContactTypeChoices],
            help=(
                "Restrict to one or more contact types. (e.g. --contact-type registrant --contact-type security)."
                "If omitted, all contact types are included.  The website currently updates registrant only."
            ),
        )

        parser.add_argument(
            "--dry-run",
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "When enabled (which is the default), does not call the registry; only reports what would be updated. "
                "Disable with --no-dry-run to perform updates."
            ),
        )

    def _build_queryset(self, *, target_domain: str, contact_types: list[str] | None):
        qs = PublicContact.objects.select_related("domain").all().order_by("id")
        qs = qs.filter(domain__name__iexact=target_domain)
        if contact_types:
            qs = qs.filter(contact_type__in=contact_types)
        return qs

    def _contact_ref(self, contact: PublicContact) -> str:
        domain_name = getattr(contact.domain, "name", "<unknown>")
        return f"db_pk={contact.pk} registry_id={contact.registry_id} domain={domain_name} type={contact.contact_type}"

    def _format_disclose(self, disclose: Any) -> str:
        flag = getattr(disclose, "flag", None)
        fields = getattr(disclose, "fields", None)
        types = getattr(disclose, "types", None)
        return f"flag={flag} fields={fields} types={types}"

    def handle(self, *args: object, **options: Any) -> None:
        contact_types = options.get("contact_type")
        dry_run = bool(options.get("dry_run", True))
        target_domain = options.get("target_domain")

        if not target_domain:
            raise ValueError("--target-domain is required")

        qs = self._build_queryset(target_domain=target_domain, contact_types=contact_types)
        total_count = qs.count()
        logger.info("Found %s PublicContact record(s) in scope.", total_count)

        proposed = (
            "==Proposed Changes==\n"
            f"Target domain: {target_domain}\n"
            f"Contact types: {contact_types or 'ALL'}\n"
            f"Dry run: {dry_run}\n\n"
            "Action: compute disclose via Domain._disclose_fields and "
            "update the registry via Domain._update_epp_contact (when not dry-run)."
        )

        if dry_run:
            logger.info(
                "%sDRY RUN:%s No registry updates will be sent.\n%s",
                TerminalColors.YELLOW,
                TerminalColors.ENDC,
                proposed,
            )
        else:
            TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=True,
                prompt_message=proposed,
                prompt_title="Update EPP disclose settings on existing PublicContacts",
            )

        processed = 0
        failed = 0

        for contact in qs.iterator():
            processed += 1
            try:
                disclose = contact.domain._disclose_fields(contact=contact)
                logger.info(
                    "%s disclose settings for %s -> %s",
                    "Would update" if dry_run else "Updating",
                    self._contact_ref(contact),
                    self._format_disclose(disclose),
                )

                if not dry_run:
                    # Computes disclose via Domain._disclose_fields and sends UpdateContact.
                    contact.domain._update_epp_contact(contact=contact)
            except Exception:
                failed += 1
                logger.exception("Failed to update disclose settings for %s", self._contact_ref(contact))

        header = (
            "FINISHED (DRY RUN): Update PublicContact disclose settings"
            if dry_run
            else "FINISHED: Update PublicContact disclose settings"
        )
        logger.info("============= %s =============", header)
        logger.info("Processed: %s", processed)
        if failed:
            logger.warning("Failed: %s", failed)
