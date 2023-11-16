"""Data migration: Send domain invitations once to existing customers."""

import argparse
import logging
import copy
import time

from django.core.management import BaseCommand
from registrar.management.commands.utility.extra_transition_domain_helper import OrganizationDataLoader
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.management.commands.utility.transition_domain_arguments import TransitionDomainArguments
from registrar.models import TransitionDomain
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from ...utility.email import send_templated_email, EmailSendingError
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
            "country_code",
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

        logger.info(
            f"{TerminalColors.MAGENTA}"
            "Loading organization data onto DomainInformation tables..."
        )
        self.update_domain_information(domain_information_to_update, args.debug)
    
    def update_domain_information(self, desired_objects: List[TransitionDomain], debug):
        di_to_update = []
        di_failed_to_update = []
        for item in desired_objects:
            # TODO - this can probably be done in fewer steps
            transition_domains = TransitionDomain.objects.filter(username=item.username, domain_name=item.domain_name)
            current_transition_domain = self.retrieve_and_assert_single_item(transition_domains, "TransitionDomain", "test")

            domains = Domain.objects.filter(name=current_transition_domain.domain_name)
            current_domain = self.retrieve_and_assert_single_item(domains, "Domain", "test")
            
            domain_informations = DomainInformation.objects.filter(domain=current_domain)
            current_domain_information = self.retrieve_and_assert_single_item(domain_informations, "DomainInformation", "test")

            try:
                # TODO - add verification to each, for instance check address_line length
                current_domain_information.address_line1 = current_transition_domain.address_line
                current_domain_information.city = current_transition_domain.city
                current_domain_information.state_territory = current_transition_domain.state_territory
                current_domain_information.zipcode = current_transition_domain.zipcode

                # TODO - Country Code
                #current_domain_information.country_code = current_transition_domain.country_code
            except Exception as err:
                logger.error(err)
                di_failed_to_update.append(current_domain_information)
            else:
                di_to_update.append(current_domain_information)
        
        if len(di_failed_to_update) > 0:
            logger.error(
                "Failed to update. An exception was encountered " 
                f"on the following TransitionDomains: {[item for item in di_failed_to_update]}"
            )
            raise Exception("Failed to update DomainInformations")

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
            #"country_code",
        ]

        DomainInformation.objects.bulk_update(di_to_update, changed_fields)

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
    
    # TODO - rename function + update so item_name_for_log works
    def retrieve_and_assert_single_item(self, item_queryset, class_name_for_log, item_name_for_log):
        """Checks if .filter returns one, and only one, item"""
        if item_queryset.count() == 0:
            # TODO - custom exception class
            raise Exception(f"Could not update. {class_name_for_log} for {item_name_for_log} was not found")
        
        if item_queryset.count() > 1:
            raise Exception(f"Could not update. Duplicate {class_name_for_log} for {item_name_for_log} was found")

        desired_item = item_queryset.get()
        return desired_item
