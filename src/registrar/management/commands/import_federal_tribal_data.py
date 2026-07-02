import argparse
import csv
import logging
import re
import requests

from django.core.management import BaseCommand
from django.core.exceptions import ValidationError

from datetime import datetime

from registrar.management.commands.utility.terminal_helper import TerminalColors
from registrar.models import FederalTribe

logger = logging.getLogger(__name__)

TRIBAL_LEADERS_CSV_URL = "https://raw.githubusercontent.com/cisagov/flat-tribal-leaders/main/tribal-leaders.csv"

# Map CSV column headers to FederalTribe model fields
CSV_FIELD_MAP = {
    "Tribe Full Name": "tribe_full_name",
    "Tribe": "tribe",
    "Tribe Alternate Name": "tribe_alternate_name",
    "First Name": "first_name",
    "Last Name": "last_name",
    "Suffix": "suffix",
    "Aka": "aka",
    "Job Title": "job_title",
    "Organization": "organization",
    "Physical Address": "address_line1",
    "City": "city",
    "State": "state_territory",
    "Zipcode": "zipcode",
    "Phone": "phone",
    "Email": "email",
    "Website": "website",
    "Date Elected": "date_elected",
    "Next Election": "next_election",
    "Notes": "notes",
}

DATE_FIELDS = {"date_elected", "next_election"}


class Command(BaseCommand):
    help = "Imports federally recognized tribal data from the Tribal Leaders CSV into the FederalTribe table."

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

    def handle(self, *args, **options):
        """
        How to run:
            ./manage.py import_federal_tribal_data --no-dry-run
            ./manage.py import_federal_tribal_data (dry run is ON by default)
        """
        dry_run = options.get("dry_run", True)
        self.warnings = []  # collect warnings across all rows
        self.skipped_rows = []  # collect skipped rows w missing tribe name

        if dry_run:
            logger.info(
                f"{TerminalColors.YELLOW}DRY RUN: No changes will be written to the database.{TerminalColors.ENDC}"
            )

        rows = self._load_csv()
        if rows is None:
            self.stderr.write(self.style.ERROR("Failed to load CSV. Aborting."))
            return

        # Tally counters, updated in place by _process_row via the counts dict
        counts = {"created": 0, "skipped": 0, "errors": 0}

        # start=2 as row 1 is the header
        for row_number, row in enumerate(rows, start=2):
            self._process_row(row, row_number, dry_run, counts)

        self._print_summary(dry_run, counts["created"], counts["skipped"], counts["errors"])
        self._print_skipped_rows()
        self._print_warnings()

    def _process_row(self, row, row_number, dry_run, counts):
        """Process a single CSV row: validate, map, then create/skip
        the corresponding FederalTribe record + updates counts in place"""
        tribe_full_name = row.get("Tribe Full Name", "").strip()

        if not tribe_full_name:
            message = f"Row {row_number} skipped — missing tribe name. " f"Row contents: {dict(row)}"
            logger.warning(message)
            self.skipped_rows.append({"row_number": row_number, "contents": dict(row)})
            counts["skipped"] += 1
            return

        try:
            mapped = self._map_row(row)

            existing = FederalTribe.objects.filter(tribe_full_name=tribe_full_name).first()

            if existing:
                logger.debug(f"'{tribe_full_name}' already exists, skipping.")
                counts["skipped"] += 1
                return

            self._create_tribe(tribe_full_name, mapped, dry_run)
            counts["created"] += 1

        except Exception as e:
            logger.error(
                f"{TerminalColors.FAIL}Error processing '{tribe_full_name}': {e}{TerminalColors.ENDC}",
                exc_info=True,
            )
            counts["errors"] += 1

    def _create_tribe(self, tribe_full_name, mapped, dry_run):
        """
        Handles the creation of a new StateTribe record.

        Parameters:
            tribe_name (str): The full name of the tribe, used for logging
            mapped (dict): A dict of cleaned model field names to values,
            ready to be passed into StateTribe.objects.create()
            dry_run (bool): If True, logs what would be created.
            If False, actually creates the record to the db.
            counts (dict): Running tally of created/skipped/error counts,
            updated in place
        Returns: None
        """
        if dry_run:
            logger.info(f"Dry run enabled...skipping creating StateTribe for '{tribe_full_name}'")
            self._log_action(dry_run, "Created", tribe_full_name, mapped)
        else:
            logger.info(f"Creating StateTribe record for '{tribe_full_name}'")
            tribe = FederalTribe(**mapped)
            try:
                tribe.full_clean()
            except ValidationError as e:
                logger.error(
                    f"{TerminalColors.FAIL}Validation failed for '{tribe_full_name}', "
                    f"skipping record. Errors: {e.message_dict}{TerminalColors.ENDC}",
                )
                raise
            else:
                tribe.save()

    def _load_csv(self):
        """Load rows rom CSV with a 30 sec timeout and make sure download succeeded
        and put into a dictionary list"""
        try:
            logger.info(f"Fetching CSV from {TRIBAL_LEADERS_CSV_URL}")
            response = requests.get(TRIBAL_LEADERS_CSV_URL, timeout=30)
            response.raise_for_status()
            decoded = response.content.decode("utf-8").splitlines()
            return list(csv.DictReader(decoded))
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}", exc_info=True)
            return None

    def _map_row(self, row):
        """Map a CSV row dict to FederalTribe model field names
        and cleans input along the way"""
        mapped = {}
        tribe_name = row.get("Tribe Full Name", "unknown").strip()
        for csv_col, model_field in CSV_FIELD_MAP.items():
            value = row.get(csv_col, "").strip() or None

            if value:
                if model_field in DATE_FIELDS:
                    value = self._parse_date(value, tribe_name)
                elif model_field == "state_territory":
                    value = self._parse_state(value, tribe_name)
                elif model_field == "phone":
                    value = self._parse_phone(value, tribe_name)
                elif model_field == "email":
                    value = self._parse_email(value, tribe_name)
                elif model_field == "zipcode" and len(value) > 10:
                    self._warn(tribe_name, f"Zipcode '{value}' exceeds 10 characters, truncating.")
                    value = value[:10]

            mapped[model_field] = value
        return mapped

    def _parse_date(self, value, tribe_name):
        """Parse into datetime.date string and handles all the different
        date types with full dates and partial month/year and sort into one unified style
        ie 9/2020 -> datetime.date(2020, 9, 1) if date not listed, 1 is default"""
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%Y", "%m-%Y", "%B %Y", "%b %Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        self._warn(tribe_name, f"Could not parse date value '{value}', storing as None.")
        return None

    def _parse_state(self, value, tribe_name):
        """Convert a full state name to its 2 letter abbrev using
        StateTerritoryChoices"""
        for choice_value, choice_label in FederalTribe.StateTerritoryChoices.choices:
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
        """
        Parse one or more email addresses from a field (, : or ;)
        and validate each one

        Parameters:
            value (str): Raw email string from the CSV field
            tribe_name (str): Name of the tribe, used for warning messages

        Returns:
            list: List of valid email strings, or None if no valid emails found
        """
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

        return valid

    def _warn(self, tribe_name, message):
        """Log warning and store it for the summary at the end"""
        full_message = f"[{tribe_name}] {message}"
        logger.warning(full_message)
        self.warnings.append(full_message)

    def _log_action(self, dry_run, action, tribe_name, fields=None):
        """Log a create action, prefixed with [DRY RUN] if applied.
        In a dry run we print out field deets"""
        prefix = "[DRY RUN] Would have " if dry_run else ""
        color = TerminalColors.YELLOW if dry_run else TerminalColors.OKGREEN

        detail = ""
        if dry_run and fields:
            field_lines = "\n".join(f"  {key}: {value}" for key, value in fields.items())
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

    def _print_skipped_rows(self):
        """Print all rows that were skipped due to missing tribe name."""
        if not self.skipped_rows:
            return

        self.stderr.write(
            f"\n{TerminalColors.YELLOW}Skipped rows with missing tribe name "
            f"({len(self.skipped_rows)} total):{TerminalColors.ENDC}"
        )
        for entry in self.skipped_rows:
            self.stderr.write(
                f"  {TerminalColors.YELLOW}- Row {entry['row_number']}: " f"{entry['contents']}{TerminalColors.ENDC}"
            )
