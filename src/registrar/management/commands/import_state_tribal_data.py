import argparse
import csv
import logging
import os
import re

from django.core.management import BaseCommand

from registrar.management.commands.utility.terminal_helper import TerminalColors
from registrar.models import StateTribe

logger = logging.getLogger(__name__)

# Map CSV column headers to StateTribe model fields
CSV_FIELD_MAP = {
    "Name": "tribe_name",
    "Recognized state": "recognized_state",
    "Authorizing legislation": "authorizing_legislation",
    "Tribal Leader First Name": "tribal_leader_first_name",
    "Tribal Leader Last Name": "tribal_leader_last_name",
    "Suffix": "suffix",
    "Evidence of tribal leader designation": "evidence_of_tribal_leader_designation",
    "Email": "email",
    "Phone": "phone",
    "Website": "website",
    "Address": "address_line1",
    "City": "city",
    "State": "state_territory",
    "Zipcode": "zipcode",
    "Date of recognition": "date_of_recognition",
    "Additional sources": "additional_sources",
    "Notes": "notes",
}

DATE_FIELDS = {"date_of_recognition"}


class Command(BaseCommand):
    help = "Imports state recognized tribal data from the state tribe CSV into the StateTribe table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "When enabled (which is the default), does NOT write to the db, only shows what would be created. "
                "Disable with --no-dry-run to perform the import."
            ),
        )
        parser.add_argument(
            "--csv-path",
            required=True,
            help="Path to the state tribe CSV file. Example: --csv-path /tmp/state_tribe.csv",
        )

    def handle(self, *args, **options):
        """
        How to run:
            ./manage.py import_state_tribal_data --csv-path /tmp/state_tribe.csv --no-dry-run
            ./manage.py import_state_tribal_data --csv-path /tmp/state_tribe.csv (dry run is on by default)
        """
        dry_run = bool(options.get("dry_run", True))
        csv_path = options.get("csv_path")
        self.warnings = []  # collect warnings across all rows

        if dry_run:
            logger.info(
                f"{TerminalColors.YELLOW}DRY RUN: No changes will be written to the database.{TerminalColors.ENDC}"
            )

        rows = self._load_csv(csv_path)
        if rows is None:
            self.stderr.write(self.style.ERROR("Failed to load CSV. Aborting."))
            return

        # Updated in place by _process_row via the counts dict
        counts = {"created": 0, "skipped": 0, "errors": 0}

        for row in rows:
            self._process_row(row, dry_run, counts)

        self._print_summary(dry_run, counts["created"], counts["skipped"], counts["errors"])
        self._print_warnings()

    def _process_row(self, row, dry_run, counts):
        """Process a single CSV row: validate, map, then create/skip
        the corresponding StateTribe record + updates counts in place"""
        tribe_name = row.get("Name", "").strip()

        if not tribe_name:
            logger.warning("Skipping row with missing Tribe Name.")
            counts["skipped"] += 1
            return

        mapped = self._map_row(row)

        try:
            existing = StateTribe.objects.filter(tribe_name=tribe_name).first()

            if existing:
                logger.debug(f"'{tribe_name}' already exists, skipping.")
                counts["skipped"] += 1
                return

            self._create_tribe(tribe_name, mapped, dry_run, counts)

        except Exception as e:
            logger.error(
                f"{TerminalColors.FAIL}Error processing '{tribe_name}': {e}{TerminalColors.ENDC}",
                exc_info=True,
            )
            counts["errors"] += 1

    def _create_tribe(self, tribe_name, mapped, dry_run, counts):
        """Handles case where no record exists yet.
        If dry run - log the action with field details.
        If not dry run - create the new StateTribe record."""
        if dry_run:
            logger.info(f"Dry run enabled...skipping creating StateTribe for '{tribe_name}'")
            self._log_action(dry_run, "Created", tribe_name, mapped)
        else:
            logger.info(f"Creating StateTribe record for '{tribe_name}'")
            StateTribe.objects.create(**mapped)
        counts["created"] += 1

    def _load_csv(self, csv_path):
        """Load rows from the CSV file at the given path and put into a dictionary list."""
        if not os.path.exists(csv_path):
            logger.error(f"CSV file not found at path: {csv_path}")
            return None
        try:
            logger.info(f"Loading CSV from {csv_path}")
            with open(csv_path, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}", exc_info=True)
            return None

    def _map_row(self, row):
        """Map a CSV row dict to StateTribe model field names
        and cleans input along the way"""
        mapped = {}
        tribe_name = row.get("Name", "unknown")
        for csv_col, model_field in CSV_FIELD_MAP.items():
            value = row.get(csv_col, "").strip() or None

            if value:
                match model_field:
                    case field if field in DATE_FIELDS:
                        value = self._parse_date(value, tribe_name)
                    case "state_territory" | "recognized_state":
                        value = self._parse_state(value, tribe_name)
                    case "phone":
                        value = self._parse_phone(value, tribe_name)
                    case "email":
                        value = self._parse_email(value, tribe_name)
                    case "zipcode" if len(value) > 10:
                        self._warn(tribe_name, f"Zipcode '{value}' exceeds 10 characters, truncating.")
                        value = value[:10]

            mapped[model_field] = value
        return mapped

    def _parse_date(self, value, tribe_name):
        """Parse into datetime.date string. Handles full dates (MM/DD/YYYY).
        Returns None on failure."""
        from datetime import datetime

        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        self._warn(tribe_name, f"Could not parse date value '{value}', storing as None.")
        return None

    def _parse_state(self, value, tribe_name):
        """Convert a full state name to its 2 letter abbrev using
        StateTerritoryChoices"""
        for choice_value, choice_label in StateTribe.StateTerritoryChoices.choices:
            # ie "Alabama (AL)", extract just "Alabama"
            plain_name = choice_label.split(" (")[0]
            if plain_name.lower() == value.lower():
                return choice_value

        self._warn(tribe_name, f"Unrecognized state value '{value}', storing as None.")
        return None

    def _parse_phone(self, value, tribe_name):
        """Strip the phone number of any other invalid info with the slash D
        and grab only the valid 10 digit US phone number"""
        digits_only = re.sub(r"\D", "", value)

        if len(digits_only) >= 10:
            cleaned = digits_only[-10:]
            return f"+1{cleaned}"

        self._warn(tribe_name, f"Phone value '{value}' could not be parsed to a valid number, storing as None.")
        return None

    def _parse_email(self, value, tribe_name):
        """Parse one or more email addresses from a field (either via , or : or ;)
        and validate each email to check if any are invalid.
        Returns a comma joined string of valid emails, or if invalid None"""
        raw_emails = re.split(r"[,;:]\s*", value)
        valid = []
        email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

        for raw in raw_emails:
            raw = raw.strip()
            if not raw:
                continue
            if email_pattern.match(raw):
                valid.append(raw)
            else:
                self._warn(tribe_name, f"Invalid email address '{raw}', skipping.")

        if not valid:
            self._warn(tribe_name, f"No valid emails found in '{value}', storing as None.")
            return None

        return ", ".join(valid)

    def _warn(self, tribe_name, message):
        """Log warning and store it for the summary at the end"""
        full_message = f"[{tribe_name}] {message}"
        logger.warning(full_message)
        self.warnings.append(full_message)

    def _log_action(self, dry_run, action, tribe_name, fields=None):
        """Log a create action, prefixed with [DRY RUN] if applied.
        Field details are only shown during dry runs."""
        prefix = "[DRY RUN] Would have " if dry_run else ""
        color = TerminalColors.YELLOW if dry_run else TerminalColors.OKGREEN

        detail = ""
        if dry_run and fields:
            field_lines = "\n".join(f"    {key}: {value}" for key, value in fields.items())
            detail = f":\n{field_lines}"

        logger.info(f"{color}{prefix}{action.lower()} '{tribe_name}'{detail}{TerminalColors.ENDC}")

    def _print_summary(self, dry_run, created, skipped, errors):
        """Print a summary of what was/will be applied"""
        prefix = "[DRY RUN] Would have applied" if dry_run else "Completed."
        summary = (
            f"\n{TerminalColors.OKBLUE}{prefix} import summary:{TerminalColors.ENDC}\n"
            f"  {TerminalColors.OKGREEN}Created : {created}{TerminalColors.ENDC}\n"
            f"  Skipped : {skipped}\n"
            f"  {TerminalColors.FAIL}Errors  : {errors}{TerminalColors.ENDC}"
        )
        if errors:
            self.stderr.write(summary)
        else:
            self.stdout.write(summary)

    def _print_warnings(self):
        """Print all collected warnings at the end of the run"""
        if not self.warnings:
            self.stdout.write(f"{TerminalColors.OKGREEN}No warnings during import.{TerminalColors.ENDC}")
            return

        self.stderr.write(f"\n{TerminalColors.YELLOW}Warnings ({len(self.warnings)} total):{TerminalColors.ENDC}")
        for warning in self.warnings:
            self.stderr.write(f"  {TerminalColors.YELLOW}- {warning}{TerminalColors.ENDC}")