"""Update registry disclose settings for existing PublicContact records.

This command is intended to update the registry with new PublicContact disclosure defaults.

- In dry-run mode (default), only logs what would be changed
- With --no-dry-run, sends registry updates via Domain._update_epp_contact
- Use --target-domain to only update an existing domain
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
    RECOVERY_LOGFILE = "update_public_contacts_recovery_log.txt"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-domain",
            "--target_domain",
            required=False,
            help="Only update contacts for a given domain name (case insensitive).",
        )

        parser.add_argument(
            "--contact-type",
            "--contact_type",
            action="append",
            required=False,
            choices=[
                PublicContact.ContactTypeChoices.REGISTRANT,
                PublicContact.ContactTypeChoices.ADMINISTRATIVE,
                PublicContact.ContactTypeChoices.SECURITY,
                PublicContact.ContactTypeChoices.TECHNICAL,
            ],
            help=("Choose one or more contact types. (e.g. --contact-type registrant --contact-type security)."),
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

        parser.add_argument(
            "--use-recovery-log",
            "--use-recovery-log",
            action=argparse.BooleanOptionalAction,
            default=False,
            help=("When enabled, use the recovery log text file to skip domains that were marked 'done'."),
        )

    def _build_queryset(self, *, target_domain: str, contact_types: list[str] | None):
        qs = (
            PublicContact.objects.select_related("domain", "domain__domain_info")
            .all()
            .order_by("domain__name", "contact_type")
        )
        qs = qs.filter(domain__name__iexact=target_domain)
        logger.debug("Query set after domain filter: %s", list(qs.values("registry_id")))
        qs = qs.filter(contact_type__in=contact_types)
        logger.debug("Query set after contact_type filter: %s", list(qs.values("registry_id")))
        return qs

    def _contact_ref(self, contact: PublicContact) -> str:
        domain_name = getattr(contact.domain, "name", "<unknown>")
        return (
            f"db_pk={contact.pk} "
            f"registry_id={contact.registry_id} "
            f"domain={domain_name} "
            f"type={contact.contact_type} "
        )

    def _check_and_update_contact_values(self, contact: PublicContact) -> PublicContact:
        if contact.contact_type == PublicContact.ContactTypeChoices.REGISTRANT:
            logger.info("Existing contact values: %s", contact)
            updated_contact = contact
            # TODO: May be legacy and not have this object
            domain_info = getattr(contact.domain, "domain_info")
            # Computes new values for Public Contact (may not be any delta, depends on if and
            # how the data relationships have changed between portfolio, domain, suborganization)
            # Returns dict of org, street1, street2, city, state_territory, zipcode
            new_values = domain_info.get_registrant_contact_data()
            updated_contact.org = new_values["org"]
            updated_contact.street1 = new_values["street1"]
            updated_contact.street2 = new_values["street2"]
            updated_contact.city = new_values["city"]
            updated_contact.sp = new_values["state_territory"]
            updated_contact.pc = new_values["zipcode"]
            logger.info("Proposed new contact values: %s", updated_contact)
            return updated_contact
        else:
            return contact

    def handle(self, *args: object, **options: Any) -> None:
        contact_types = options.get("contact_type")
        if not contact_types:
            raise ValueError("--contact-types is required")
        # if one contact type was passed in, convert to a list
        elif isinstance(contact_types, str):
            contact_types = [contact_types]

        dry_run = bool(options.get("dry_run", True))
        target_domain = options.get("target_domain")
        if not target_domain:
            raise ValueError("--target-domain is required")

        use_recovery_log = bool(options.get("-use-recovery-log", False))

        logger.info("Building queryset for: %s, %s", contact_types, target_domain)
        contacts_to_update = self._build_queryset(
            target_domain=target_domain,
            contact_types=contact_types,
        )
        total_count = contacts_to_update.count()
        logger.info("Found %s PublicContact record(s) in scope.", total_count)

        proposed = (
            "==Proposed Changes==\n"
            f"Target domain: {target_domain}\n"
            f"Contact types: {contact_types}\n"
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
        current_domain = None

        log_filename = self.RECOVERY_LOGFILE

        for contact in contacts_to_update.iterator():
            processed += 1
            if current_domain != contact.domain.name:
                current_domain = contact.domain.name

            if use_recovery_log:
                with open(log_filename, "r") as logfile:
                    line = logfile.readline()
                    if line.endswith("done"):
                        continue
            else:
                with open(log_filename, "w") as logfile:
                    logfile.write(f"{current_domain},")

            failed += self._do_update(dry_run, use_recovery_log, log_filename, contact)

        header = (
            "FINISHED (DRY RUN): Update PublicContact disclose settings"
            if dry_run
            else "FINISHED: Update PublicContact disclose settings"
        )
        logger.info("============= %s =============", header)
        logger.info("Processed: %s", processed)
        if failed:
            logger.warning("Failed: %s", failed)

    def _do_update(self, dry_run, use_recovery_log, log_filename, contact):
        failed = 0
        try:
            contact = self._check_and_update_contact_values(contact)

            existing_contact = contact.domain._request_contact_info(contact)
            existing_disclose = existing_contact.disclose
            logger.info("Existing disclose for %s: %s", self._contact_ref(contact), existing_disclose)
            disclose = contact.domain._disclose_fields(contact=contact)
            logger.info("Proposed new disclose for %s: %s", self._contact_ref(contact), disclose)

            if dry_run:
                logger.info("Would update, but skipping because dry_run = True")
            else:
                logger.info("Updating %s on registry", self._contact_ref(contact))
                # Computes disclose via Domain._disclose_fields and sends UpdateContact.
                contact.domain._update_epp_contact(contact=contact)
                if not use_recovery_log:
                    with open(log_filename, "a") as logfile:
                        logfile.write("done\n")
        except Exception:
            failed += 1
            logger.exception(
                "Failed to update disclose settings for %s on registry",
                self._contact_ref(contact),
            )
            if not use_recovery_log:
                with open(log_filename, "a") as logfile:
                    logfile.write("error\n")
        return failed
