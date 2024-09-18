"""Data migration: Load organization data for TransitionDomain and DomainInformation objects"""

import argparse
import json
import logging
import os

from django.core.management import BaseCommand
from registrar.management.commands.utility.extra_transition_domain_helper import OrganizationDataLoader
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.management.commands.utility.transition_domain_arguments import TransitionDomainArguments
from registrar.models import TransitionDomain, DomainInformation
from django.core.paginator import Paginator
from typing import List
from registrar.models.domain import Domain

from registrar.management.commands.utility.load_organization_error import (
    LoadOrganizationError,
    LoadOrganizationErrorCodes,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load organization data on TransitionDomain and DomainInformation objects"

    def __init__(self):
        super().__init__()
        self.domain_information_to_update: List[DomainInformation] = []

        # Stores the domain_name for logging purposes
        self.domains_failed_to_update: List[str] = []
        self.domains_skipped: List[str] = []

        self.changed_fields = [
            "address_line1",
            "city",
            "state_territory",
            "zipcode",
        ]

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.add_argument(
            "migration_json_filename",
            help=("A JSON file that holds the location and filenames" "of all the data files used for migrations"),
        )

        parser.add_argument("--sep", default="|", help="Delimiter character")

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument("--directory", default="migrationdata", help="Desired directory")

    def handle(self, migration_json_filename, **options):
        """Load organization address data into the TransitionDomain
        and DomainInformation tables by using the organization adhoc file and domain_additional file"""
        # Parse JSON file
        options = self.load_json_settings(options, migration_json_filename)
        org_args = TransitionDomainArguments(**options)

        # Will sys.exit() when prompt is "n"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            ==Master data file==
            domain_additional_filename: {org_args.domain_additional_filename}

            ==Organization data==
            organization_adhoc_filename: {org_args.organization_adhoc_filename}

            ==Containing directory==
            directory: {org_args.directory}
            """,
            prompt_title="Do you wish to load organization data for TransitionDomains?",
        )

        org_load_helper = OrganizationDataLoader(org_args)
        transition_domains = org_load_helper.update_organization_data_for_all()

        # Reprompt the user to reinspect before updating DomainInformation
        # Will sys.exit() when prompt is "n"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=f"""
            ==Master data file==
            domain_additional_filename: {org_args.domain_additional_filename}

            ==Organization name information==
            organization_adhoc_filename: {org_args.organization_adhoc_filename}

            ==Containing directory==
            directory: {org_args.directory}

            ==Proposed Changes==
            Number of DomainInformation objects to (potentially) change: {len(transition_domains)}
            For each DomainInformation, modify the following fields: {self.changed_fields}
            """,
            prompt_title="Do you wish to update organization address data for DomainInformation as well?",
        )

        logger.info(
            f"{TerminalColors.MAGENTA}"
            "Preparing to load organization data onto DomainInformation tables..."
            f"{TerminalColors.ENDC}"
        )
        self.prepare_update_domain_information(transition_domains, org_args.debug)

        logger.info(f"{TerminalColors.MAGENTA}" f"Beginning mass DomainInformation update..." f"{TerminalColors.ENDC}")
        self.bulk_update_domain_information(org_args.debug)

    def load_json_settings(self, options, migration_json_filename):
        """Parses options from the given JSON file."""
        json_filepath = os.path.join(options["directory"], migration_json_filename)

        # If a JSON was provided, use its values instead of defaults.
        with open(json_filepath, "r") as jsonFile:
            # load JSON object as a dictionary
            try:
                data = json.load(jsonFile)

                skipped_fields = ["domain_additional_filename", "organization_adhoc_filename"]
                # Iterate over the data from the JSON file. Skip any unused values.
                for key, value in data.items():
                    if value is not None and value.strip() != "":
                        # If any key in skipped_fields has a value, then
                        # we override what is specified in the JSON.
                        if options not in skipped_fields:
                            options[key] = value

            except Exception as err:
                logger.error(
                    f"{TerminalColors.FAIL}"
                    "There was an error loading "
                    "the JSON responsible for providing filepaths."
                    f"{TerminalColors.ENDC}"
                )
                raise err

            return options

    def prepare_update_domain_information(self, target_transition_domains: List[TransitionDomain], debug):
        """Returns an array of DomainInformation objects with updated organization data."""
        if len(target_transition_domains) == 0:
            raise LoadOrganizationError(code=LoadOrganizationErrorCodes.EMPTY_TRANSITION_DOMAIN_TABLE)

        # Grab each TransitionDomain we want to change.
        transition_domains = TransitionDomain.objects.filter(
            username__in=[item.username for item in target_transition_domains],
            domain_name__in=[item.domain_name for item in target_transition_domains],
        )

        # This indicates that some form of data corruption happened.
        if len(target_transition_domains) != len(transition_domains):
            raise LoadOrganizationError(code=LoadOrganizationErrorCodes.TRANSITION_DOMAINS_NOT_FOUND)

        # Maps TransitionDomain <--> DomainInformation.
        # If any related organization fields have been updated,
        # we can assume that they modified this information themselves - thus we should not update it.
        domain_informations = DomainInformation.objects.filter(
            domain__name__in=[td.domain_name for td in transition_domains],
            address_line1__isnull=True,
            city__isnull=True,
            state_territory__isnull=True,
            zipcode__isnull=True,
        )
        filtered_domain_informations_dict = {di.domain.name: di for di in domain_informations if di.domain is not None}

        # === Create DomainInformation objects === #
        for item in transition_domains:
            self.map_transition_domain_to_domain_information(item, filtered_domain_informations_dict, debug)

        # === Log results and return data === #
        if len(self.domains_failed_to_update) > 0:
            logger.error(
                f"""{TerminalColors.FAIL}
                Failed to update. An exception was encountered on the following Domains: {self.domains_failed_to_update}
                {TerminalColors.ENDC}"""
            )
            raise LoadOrganizationError(code=LoadOrganizationErrorCodes.UPDATE_DOMAIN_INFO_FAILED)

        if debug:
            logger.info(f"Updating these DomainInformations: {[item for item in self.domain_information_to_update]}")

        if len(self.domains_skipped) > 0:
            logger.info(f"Skipped these fields: {self.domains_skipped}")
            logger.info(
                f"{TerminalColors.YELLOW}"
                f"Skipped updating {len(self.domains_skipped)} fields. User-supplied data exists, or there is no data."
                f"{TerminalColors.ENDC}"
            )

        logger.info(f"Ready to update {len(self.domain_information_to_update)} DomainInformations.")

        return self.domain_information_to_update

    def bulk_update_domain_information(self, debug):
        """Performs a bulk_update operation on a list of DomainInformation objects"""
        # Create a Paginator object. Bulk_update on the full dataset
        # is too memory intensive for our current app config, so we can chunk this data instead.
        batch_size = 1000
        paginator = Paginator(self.domain_information_to_update, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            DomainInformation.objects.bulk_update(page.object_list, self.changed_fields)

        if debug:
            logger.info(f"Updated these DomainInformations: {[item for item in self.domain_information_to_update]}")

        logger.info(
            f"{TerminalColors.OKGREEN}"
            f"Updated {len(self.domain_information_to_update)} DomainInformations."
            f"{TerminalColors.ENDC}"
        )

    def map_transition_domain_to_domain_information(self, item, domain_informations_dict, debug):
        """Attempts to return a DomainInformation object based on values from TransitionDomain.
        Any domains which cannot be updated will be stored in an array.
        """
        does_not_exist: bool = self.is_domain_name_missing(item, domain_informations_dict)
        all_fields_are_none: bool = self.is_organization_data_missing(item)
        if does_not_exist:
            self.handle_if_domain_name_missing(item.domain_name)
        elif all_fields_are_none:
            logger.info(
                f"{TerminalColors.YELLOW}"
                f"Domain {item.domain_name} has no Organization Data. Cannot update."
                f"{TerminalColors.ENDC}"
            )
            self.domains_skipped.append(item.domain_name)
        else:
            # Based on the current domain, grab the right DomainInformation object.
            current_domain_information = domain_informations_dict[item.domain_name]
            if current_domain_information.domain is None or current_domain_information.domain.name is None:
                raise LoadOrganizationError(code=LoadOrganizationErrorCodes.DOMAIN_NAME_WAS_NONE)

            # Update fields
            current_domain_information.address_line1 = item.address_line
            current_domain_information.city = item.city
            current_domain_information.state_territory = item.state_territory
            current_domain_information.zipcode = item.zipcode
            self.domain_information_to_update.append(current_domain_information)

            if debug:
                logger.info(f"Updated {current_domain_information.domain.name}...")

    def is_domain_name_missing(self, item: TransitionDomain, domain_informations_dict):
        """Checks if domain_name is in the supplied dictionary"""
        return item.domain_name not in domain_informations_dict

    def is_organization_data_missing(self, item: TransitionDomain):
        """Checks if all desired Organization fields to update are none"""
        fields = [item.address_line, item.city, item.state_territory, item.zipcode]
        return all(field is None for field in fields)

    def handle_if_domain_name_missing(self, domain_name):
        """
        Infers what to log if we can't find a domain_name and updates the relevant lists.

        This function performs the following checks:
        1. If the domain does not exist, it logs an error and adds the domain name to the `domains_failed_to_update` list.
        2. If the domain was updated by a user, it logs an info message and adds the domain name to the `domains_skipped` list.
        3. If there are duplicate domains, it logs an error and adds the domain name to the `domains_failed_to_update` list.

        Args:
            domain_name (str): The name of the domain to check.
        """  # noqa - E501 (harder to read)
        domains = Domain.objects.filter(name=domain_name)
        if domains.count() == 0:
            logger.error(f"Could not add {domain_name}. Domain does not exist.")
            self.domains_failed_to_update.append(domain_name)
        elif domains.count() == 1:
            logger.info(
                f"{TerminalColors.YELLOW}"
                f"Domain {domain_name} was updated by a user. Cannot update."
                f"{TerminalColors.ENDC}"
            )
            self.domains_skipped.append(domain_name)
        else:
            logger.error(f"Could not add {domain_name}. Duplicate domains exist.")
            self.domains_failed_to_update.append(domain_name)
