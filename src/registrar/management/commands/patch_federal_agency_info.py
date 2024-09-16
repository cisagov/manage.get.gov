"""Loops through each valid DomainInformation object and updates its agency value"""

import argparse
import csv
import logging
import os
from typing import List

from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models.domain_information import DomainInformation
from django.db.models import Q

from registrar.models.transition_domain import TransitionDomain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Loops through each valid DomainInformation object and updates its agency value"

    def __init__(self):
        super().__init__()
        self.di_to_update: List[DomainInformation] = []
        self.di_failed_to_update: List[DomainInformation] = []
        self.di_skipped: List[DomainInformation] = []

    def add_arguments(self, parser):
        """Adds command line arguments"""
        parser.add_argument(
            "current_full_filepath",
            help="TBD",
        )
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)
        parser.add_argument("--sep", default=",", help="Delimiter character")

    def handle(self, current_full_filepath, **kwargs):
        """Loops through each valid DomainInformation object and updates its agency value"""
        debug = kwargs.get("debug")
        separator = kwargs.get("sep")

        # Check if the provided file path is valid
        if not os.path.isfile(current_full_filepath):
            raise argparse.ArgumentTypeError(f"Invalid file path '{current_full_filepath}'")

        # === Update the "federal_agency" field === #
        was_success = self.patch_agency_info(debug)

        # === Try to process anything that was skipped === #
        # We should only correct skipped records if the previous step was successful.
        # If something goes wrong, then we risk corrupting data, so skip this step.
        if len(self.di_skipped) > 0 and was_success:
            # Flush out the list of DomainInformations to update
            self.di_to_update.clear()
            self.process_skipped_records(current_full_filepath, separator, debug)

            # Clear the old skipped list, and log the run summary
            self.di_skipped.clear()
            self.log_script_run_summary(debug)
        elif not was_success:
            # This code should never execute. This can only occur if bulk_update somehow fails,
            # which may indicate some sort of data corruption.
            logger.error(
                f"{TerminalColors.FAIL}"
                "Could not automatically patch skipped records. The initial update failed."
                "An error was encountered when running this script, please inspect the following "
                f"records for accuracy and completeness: {self.di_failed_to_update}"
                f"{TerminalColors.ENDC}"
            )

    def patch_agency_info(self, debug):
        """
        Updates the federal_agency field of each valid DomainInformation object based on the corresponding
        TransitionDomain object. Skips the update if the TransitionDomain object does not exist or its
        federal_agency field is None. Logs the update, skip, and failure actions if debug mode is on.
        After all updates, logs a summary of the results.
        """

        # Grab all DomainInformation objects (and their associated TransitionDomains)
        # that need to be updated
        empty_agency_query = Q(federal_agency=None) | Q(federal_agency="")
        domain_info_to_fix = DomainInformation.objects.filter(empty_agency_query)

        domain_names = domain_info_to_fix.values_list("domain__name", flat=True)
        transition_domains = TransitionDomain.objects.filter(domain_name__in=domain_names).exclude(empty_agency_query)

        # Get the domain names from TransitionDomain
        td_agencies = transition_domains.values_list("domain_name", "federal_agency").distinct()

        human_readable_domain_names = list(domain_names)
        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            ==Proposed Changes==
            Number of DomainInformation objects to change: {len(human_readable_domain_names)}
            The following DomainInformation objects will be modified: {human_readable_domain_names}
            """,
            prompt_title="Do you wish to patch federal_agency data?",
        )
        logger.info("Updating...")

        # Create a dictionary mapping of domain_name to federal_agency
        td_dict = dict(td_agencies)

        for di in domain_info_to_fix:
            domain_name = di.domain.name
            federal_agency = td_dict.get(domain_name)
            log_message = None

            # If agency exists on a TransitionDomain, update the related DomainInformation object
            if domain_name in td_dict:
                di.federal_agency = federal_agency
                self.di_to_update.append(di)
                log_message = f"{TerminalColors.OKCYAN}Updated {di}{TerminalColors.ENDC}"
            else:
                self.di_skipped.append(di)
                log_message = f"{TerminalColors.YELLOW}Skipping update for {di}{TerminalColors.ENDC}"

            # Log the action if debug mode is on
            if debug and log_message is not None:
                logger.info(log_message)

        # Bulk update the federal agency field in DomainInformation objects
        DomainInformation.objects.bulk_update(self.di_to_update, ["federal_agency"])

        # Get a list of each domain we changed
        corrected_domains = DomainInformation.objects.filter(domain__name__in=domain_names)

        # After the update has happened, do a sweep of what we get back.
        # If the fields we expect to update are still None, then something is wrong.
        for di in corrected_domains:
            if di not in self.di_skipped and di.federal_agency is None:
                logger.info(f"{TerminalColors.FAIL}Failed to update {di}{TerminalColors.ENDC}")
                self.di_failed_to_update.append(di)

        # === Log results and return data === #
        self.log_script_run_summary(debug)
        # Tracks if this script was successful. If any errors are found, something went very wrong.
        was_success = len(self.di_failed_to_update) == 0
        return was_success

    def process_skipped_records(self, file_path, separator, debug):
        """If we encounter any DomainInformation records that do not have data in the associated
        TransitionDomain record, then check the associated current-full.csv file for this
        information."""

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            ==File location==
            current-full.csv filepath: {file_path}

            ==Proposed Changes==
            Number of DomainInformation objects to change: {len(self.di_skipped)}
            The following DomainInformation objects will be modified if agency data exists in file: {self.di_skipped}
            """,
            prompt_title="Do you wish to patch skipped records?",
        )
        logger.info("Updating...")

        file_data = self.read_current_full(file_path, separator)
        for di in self.di_skipped:
            domain_name = di.domain.name
            row = file_data.get(domain_name)
            fed_agency = None
            if row is not None and "agency" in row:
                fed_agency = row.get("agency")

            # Determine if we should update this record or not.
            # If we don't get any data back, something went wrong.
            if fed_agency is not None:
                di.federal_agency = fed_agency
                self.di_to_update.append(di)
                if debug:
                    logger.info(f"{TerminalColors.OKCYAN}" f"Updating {di}" f"{TerminalColors.ENDC}")
            else:
                self.di_failed_to_update.append(di)
                logger.error(
                    f"{TerminalColors.FAIL}" f"Could not update {di}. No information found." f"{TerminalColors.ENDC}"
                )

        # Bulk update the federal agency field in DomainInformation objects
        DomainInformation.objects.bulk_update(self.di_to_update, ["federal_agency"])

    def read_current_full(self, file_path, separator):
        """Reads the current-full.csv file and stores it in a dictionary"""
        with open(file_path, "r") as requested_file:
            old_reader = csv.DictReader(requested_file, delimiter=separator)
            # Some variants of current-full.csv have key casing differences for fields
            # such as "Domain name" or "Domain Name". This corrects that.
            reader = self.lowercase_fieldnames(old_reader)
            # Return a dictionary with the domain name as the key,
            # and the row information as the value
            dict_data = {}
            for row in reader:
                domain_name = row.get("domain name")
                if domain_name is not None:
                    domain_name = domain_name.lower()
                    dict_data[domain_name] = row

            return dict_data

    def lowercase_fieldnames(self, reader):
        """Lowercases all field keys in a dictreader to account for potential casing differences"""
        for row in reader:
            yield {k.lower(): v for k, v in row.items()}

    def log_script_run_summary(self, debug):
        """Prints success, failed, and skipped counts, as well as
        all affected objects."""
        update_success_count = len(self.di_to_update)
        update_failed_count = len(self.di_failed_to_update)
        update_skipped_count = len(self.di_skipped)

        # Prepare debug messages
        debug_messages = {
            "success": (f"{TerminalColors.OKCYAN}Updated: {self.di_to_update}{TerminalColors.ENDC}\n"),
            "skipped": (f"{TerminalColors.YELLOW}Skipped: {self.di_skipped}{TerminalColors.ENDC}\n"),
            "failed": (f"{TerminalColors.FAIL}Failed: {self.di_failed_to_update}{TerminalColors.ENDC}\n"),
        }

        # Print out a list of everything that was changed, if we have any changes to log.
        # Otherwise, don't print anything.
        TerminalHelper.print_conditional(
            debug,
            f"{debug_messages.get('success') if update_success_count > 0 else ''}"
            f"{debug_messages.get('skipped') if update_skipped_count > 0 else ''}"
            f"{debug_messages.get('failed') if update_failed_count > 0 else ''}",
        )

        if update_failed_count == 0 and update_skipped_count == 0:
            logger.info(
                f"""{TerminalColors.OKGREEN}
                ============= FINISHED ===============
                Updated {update_success_count} DomainInformation entries
                {TerminalColors.ENDC}
                """
            )
        elif update_failed_count == 0:
            logger.warning(
                f"""{TerminalColors.YELLOW}
                ============= FINISHED ===============
                Updated {update_success_count} DomainInformation entries

                ----- SOME AGENCY DATA WAS NONE (WILL BE PATCHED AUTOMATICALLY) -----
                Skipped updating {update_skipped_count} DomainInformation entries
                {TerminalColors.ENDC}
                """
            )
        else:
            logger.error(
                f"""{TerminalColors.FAIL}
                ============= FINISHED ===============
                Updated {update_success_count} DomainInformation entries

                ----- UPDATE FAILED -----
                Failed to update {update_failed_count} DomainInformation entries,
                Skipped updating {update_skipped_count} DomainInformation entries
                {TerminalColors.ENDC}
                """
            )
