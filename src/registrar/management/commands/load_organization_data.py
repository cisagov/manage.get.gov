"""Data migration: Send domain invitations once to existing customers."""

import argparse
import logging

from django.core.management import BaseCommand
from registrar.management.commands.utility.extra_transition_domain_helper import OrganizationDataLoader
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.management.commands.utility.transition_domain_arguments import TransitionDomainArguments
from registrar.models import TransitionDomain
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from django.core.paginator import Paginator
from typing import List

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send domain invitations once to existing customers."

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.add_argument("--sep", default="|", help="Delimiter character")

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument("--directory", default="migrationdata", help="Desired directory")

        parser.add_argument(
            "--domain_additional_filename",
            help="Defines the filename for additional domain data",
            required=True,
        )

        parser.add_argument(
            "--organization_adhoc_filename",
            help="Defines the filename for domain type adhocs",
            required=True,
        )

    def handle(self, **options):
        """Process the objects in TransitionDomain."""
        args = TransitionDomainArguments(**options)

        changed_fields = [
            "address_line",
            "city",
            "state_territory",
            "zipcode",
        ]
        proceed = TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Master data file==
            domain_additional_filename: {args.domain_additional_filename}

            ==Organization name information==
            organization_adhoc_filename: {args.organization_adhoc_filename}

            ==Containing directory==
            directory: {args.directory}

            ==Proposed Changes==
            For each TransitionDomain, modify the following fields: {changed_fields}
            """,
            prompt_title="Do you wish to load organization data for TransitionDomains?",
        )

        if not proceed:
            return None

        logger.info(
            f"{TerminalColors.MAGENTA}"
            "Loading organization data onto TransitionDomain tables..."
        )
        load = OrganizationDataLoader(args)
        domain_information_to_update = load.update_organization_data_for_all()

        # Reprompt the user to reinspect before updating DomainInformation
        proceed = TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Master data file==
            domain_additional_filename: {args.domain_additional_filename}

            ==Organization name information==
            organization_adhoc_filename: {args.organization_adhoc_filename}

            ==Containing directory==
            directory: {args.directory}

            ==Proposed Changes==
            Number of DomainInformation objects to change: {len(domain_information_to_update)}
            """,
            prompt_title="Do you wish to load organization data for DomainInformation?",
        )

        if not proceed:
            return None

        if len(domain_information_to_update) == 0:
            logger.error(
                f"{TerminalColors.MAGENTA}"
                "No DomainInformation objects exist"
                f"{TerminalColors.ENDC}"
            )
            return None

        logger.info(
            f"{TerminalColors.MAGENTA}"
            "Preparing to load organization data onto DomainInformation tables..."
            f"{TerminalColors.ENDC}"
        )
        self.update_domain_information(domain_information_to_update, args.debug)
    
    def update_domain_information(self, desired_objects: List[TransitionDomain], debug):
        di_to_update = []
        di_failed_to_update = []
        # These are fields that we COULD update, but fields we choose not to update.
        # For instance, if the user already entered data - lets not corrupt that.
        di_skipped = []

        # Grab each TransitionDomain we want to change. Store it.
        # Fetches all TransitionDomains in one query.
        transition_domains = TransitionDomain.objects.filter(
            username__in=[item.username for item in desired_objects],
            domain_name__in=[item.domain_name for item in desired_objects]
        ).distinct()

        if len(desired_objects) != len(transition_domains):
            raise Exception("Could not find all desired TransitionDomains")

        # Then, for each domain_name grab the associated domain object.
        # Fetches all Domains in one query.
        domains = Domain.objects.filter(
            name__in=[td.domain_name for td in transition_domains]
        )


        # Start with all DomainInformation objects
        filtered_domain_informations = DomainInformation.objects.all()
        
        changed_fields = [
            "address_line1",
            "city",
            "state_territory",
            "zipcode",
        ]

        # Chain filter calls for each field. This checks to see if the end user
        # made a change to ANY field in changed_fields. If they did, don't update their information.
        # We assume that if they made a change, we don't want to interfere with that.
        for field in changed_fields:
            # For each changed_field, check if no data exists
            filtered_domain_informations = filtered_domain_informations.filter(**{f'{field}__isnull': True})

        # Then, use each domain object to map domain <--> DomainInformation
        # Fetches all DomainInformations in one query.
        domain_informations = filtered_domain_informations.filter(
            domain__in=domains
        )

        # Create dictionaries for faster lookup
        domains_dict = {d.name: d for d in domains}
        domain_informations_dict = {di.domain.name: di for di in domain_informations}

        for item in transition_domains:
            try:
                should_update = True
                # Grab the current Domain. This ensures we are pointing towards the right place.
                current_domain = domains_dict[item.domain_name]

                # Based on the current domain, grab the right DomainInformation object.
                if current_domain.name in domain_informations_dict:
                    current_domain_information = domain_informations_dict[current_domain.name]
                    current_domain_information.address_line1 = item.address_line
                    current_domain_information.city = item.city
                    current_domain_information.state_territory = item.state_territory
                    current_domain_information.zipcode = item.zipcode
                    
                    if debug:
                        logger.info(f"Updating {current_domain.name}...")

                else:
                    logger.info(
                        f"{TerminalColors.YELLOW}"
                        f"Domain {current_domain.name} was updated by a user. Cannot update."
                        f"{TerminalColors.ENDC}"
                    )
                    should_update = False

            except Exception as err:
                logger.error(err)
                di_failed_to_update.append(item)
            else:
                if should_update:
                    di_to_update.append(current_domain_information)
                else:
                    # TODO either update to name for all,
                    # or have this filter to the right field
                    di_skipped.append(item)
        
        if len(di_failed_to_update) > 0:
            logger.error(
                f"{TerminalColors.FAIL}"
                "Failed to update. An exception was encountered " 
                f"on the following TransitionDomains: {[item for item in di_failed_to_update]}"
                f"{TerminalColors.ENDC}"
            )
            raise Exception("Failed to update DomainInformations")
        
        skipped_count = len(di_skipped)
        if skipped_count > 0:
            logger.info(f"Skipped updating {skipped_count} fields. User-supplied data exists")

        if not debug:
            logger.info(
                f"Ready to update {len(di_to_update)} TransitionDomains."
            )
        else:
            logger.info(
                f"Ready to update {len(di_to_update)} TransitionDomains: {[item for item in di_to_update]}"
            )
        
        logger.info(
            f"{TerminalColors.MAGENTA}"
            "Beginning mass DomainInformation update..."
            f"{TerminalColors.ENDC}"
        )

        changed_fields = [
            "address_line1",
            "city",
            "state_territory",
            "zipcode",
        ]

        batch_size = 1000
        # Create a Paginator object. Bulk_update on the full dataset
        # is too memory intensive for our current app config, so we can chunk this data instead.
        paginator = Paginator(di_to_update, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            DomainInformation.objects.bulk_update(page.object_list, changed_fields)

        if not debug:
            logger.info(
                f"{TerminalColors.OKGREEN}"
                f"Updated {len(di_to_update)} DomainInformations."
                f"{TerminalColors.ENDC}"
            )
        else:
            logger.info(
                f"{TerminalColors.OKGREEN}"
                f"Updated {len(di_to_update)} DomainInformations: {[item for item in di_to_update]}"
                f"{TerminalColors.ENDC}"
            )
