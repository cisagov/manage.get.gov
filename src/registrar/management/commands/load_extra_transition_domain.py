""""""
import csv
import glob
import re
import logging

import os
from typing import List
from enum import Enum
from django.core.management import BaseCommand

from registrar.models.transition_domain import TransitionDomain
from .utility.extra_transition_domain import ExtraTransitionDomain
from .utility.epp_data_containers import (
    AgencyAdhoc,
    AuthorityAdhoc,
    DomainAdditionalData,
    DomainTypeAdhoc,
    OrganizationAdhoc,
    EnumFilenames,
)

logger = logging.getLogger(__name__)


class LogCode(Enum):
    ERROR = 1
    WARNING = 2
    INFO = 3
    DEBUG = 4


class FileTransitionLog:
    """Container for storing event logs. Used to lessen
    the complexity of storing multiple logs across multiple 
    variables. 
    
    self.logs: dict -> {
        EnumFilenames.DOMAIN_ADHOC: List[LogItem],
        EnumFilenames.AGENCY_ADHOC: List[LogItem],
        EnumFilenames.ORGANIZATION_ADHOC: List[LogItem],
        EnumFilenames.DOMAIN_ADDITIONAL: List[LogItem],
    }
    """
    def __init__(self):
        self.logs = {
            EnumFilenames.DOMAIN_ADHOC: [],
            EnumFilenames.AGENCY_ADHOC: [],
            EnumFilenames.ORGANIZATION_ADHOC: [],
            EnumFilenames.DOMAIN_ADDITIONAL: [],
        }

    class LogItem:
        """Used for storing data about logger information.
        Intended for use in"""
        def __init__(self, file_type, code, message):
            self.file_type = file_type
            self.code = code
            self.message = message

    def add_log(self, file_type, code, message):
        """Adds a log item to self.logs

        file_type -> Which array to add to, 
        ex. EnumFilenames.DOMAIN_ADHOC

        code -> Log severity or other metadata, ex. LogCode.ERROR

        message -> Message to display
        """
        self.logs[file_type] = self.LogItem(file_type, code, message)

    def create_log_item(self, file_type, code, message, add_to_list=True):
        """Creates and returns an LogItem object.

        add_to_list: bool -> If enabled, add it to the logs array.
        """
        log = self.LogItem(file_type, code, message)
        if not add_to_list:
            return log
        else:
            self.logs[file_type] = log
        return log

    def display_logs(self, file_type):
        """Displays all logs in the given file_type in EnumFilenames.
        Will log with the correct severity depending on code.
        """
        for log in self.logs.get(file_type):
            match log.code:
                case LogCode.ERROR:
                    logger.error(log.message)
                case LogCode.WARNING:
                    logger.warning(log.message)
                case LogCode.INFO:
                    logger.info(log.message)
                case LogCode.DEBUG:
                    logger.debug(log.message)


class Command(BaseCommand):
    help = ""
    filenames = EnumFilenames
    parse_logs = FileTransitionLog()

    def add_arguments(self, parser):
        """Add filename arguments."""
        parser.add_argument(
            "--directory", default="migrationdata", help="Desired directory"
        )
        parser.add_argument(
            "--agency_adhoc_filename",
            default=EnumFilenames.AGENCY_ADHOC[1],
            help="Defines the filename for agency adhocs",
        )
        parser.add_argument(
            "--domain_additional_filename",
            default=EnumFilenames.DOMAIN_ADDITIONAL[1],
            help="Defines the filename for additional domain data",
        )
        parser.add_argument(
            "--domain_adhoc_filename",
            default=EnumFilenames.DOMAIN_ADHOC[1],
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument(
            "--organization_adhoc_filename",
            default=EnumFilenames.ORGANIZATION_ADHOC[1],
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument("--sep", default="|", help="Delimiter character")

    def handle(self, **options):
        try:
            self.domain_object = ExtraTransitionDomain(
                agency_adhoc_filename=options["agency_adhoc_filename"],
                domain_additional_filename=options["domain_additional_filename"],
                domain_adhoc_filename=options["domain_adhoc_filename"],
                organization_adhoc_filename=options["organization_adhoc_filename"],
                directory=options["directory"],
                seperator=options["sep"],
            )
            self.domain_object.parse_all_files()
        except Exception as err:
            logger.error(f"Could not load additional data. Error: {err}")
        else:
            all_transition_domains = TransitionDomain.objects.all()
            if not all_transition_domains.exists():
                raise Exception("No TransitionDomain objects exist.")

            for transition_domain in all_transition_domains:
                domain_name = transition_domain.domain_name
                updated_transition_domain = transition_domain

                # STEP 1: Parse organization data
                updated_transition_domain = self.parse_org_data(
                    domain_name, transition_domain
                )
                self.parse_logs.display_logs(EnumFilenames.ORGANIZATION_ADHOC)

                # STEP 2: Parse domain type data
                updated_transition_domain = self.parse_domain_type_data(
                    domain_name, transition_domain
                )
                self.parse_logs.display_logs(EnumFilenames.DOMAIN_ADHOC)

                # STEP 3: Parse agency data - TODO
                updated_transition_domain = self.parse_agency_data(
                    domain_name, transition_domain
                )
                self.parse_logs.display_logs(EnumFilenames.AGENCY_ADHOC)

                # STEP 4: Parse expiration data - TODO
                updated_transition_domain = self.parse_expiration_data(
                    domain_name, transition_domain
                )
                # self.parse_logs(EnumFilenames.EXPIRATION_DATA)

                updated_transition_domain.save()

    # TODO - Implement once Niki gets her ticket in
    def parse_expiration_data(self, domain_name, transition_domain):
        return transition_domain

    def parse_agency_data(self, domain_name, transition_domain) -> TransitionDomain:
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        info = self.get_agency_info(domain_name)
        if info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.AGENCY_ADHOC,
                LogCode.INFO,
                f"Could not add federal_agency on {domain_name}, no data exists."
            )
            return transition_domain

        agency_exists = (
            transition_domain.federal_agency is not None
            and transition_domain.federal_agency.strip() != ""
        )

        if not info.active.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add inactive agency {info.agencyname} on {domain_name}",
            )
            return transition_domain
        
        if not info.isfederal.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add non-federal agency {info.agencyname} on {domain_name}",
            )
            return transition_domain
        
        transition_domain.federal_agency = info.agencyname

        # Logs if we either added to this property,
        # or modified it.
        self._add_or_change_message(
            EnumFilenames.AGENCY_ADHOC,
            "federal_agency",
            transition_domain.federal_agency,
            domain_name,
            agency_exists
        )

        return transition_domain

    def parse_domain_type_data(self, domain_name, transition_domain: TransitionDomain) -> TransitionDomain:
        """Parses the DomainType file. 
        This file has definitions for organization_type and federal_agency.
        Logs if 
        """
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        info = self.get_domain_type_info(domain_name)
        if info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.INFO,
                f"Could not add domain_type on {domain_name}, no data exists.",
            )
            return transition_domain

        # This data is stored as follows: FEDERAL - Judicial
        # For all other records, it is stored as so: Interstate
        # We can infer if it is federal or not based on this fact.
        domain_type = info.domaintype.split("-")
        if domain_type.count != 1 or domain_type.count != 2:
            raise ValueError("Found invalid data in DOMAIN_ADHOC")

        # Then, just grab the organization type.
        new_organization_type = domain_type[0].strip()

        # Check if this domain_type is active or not.
        # If not, we don't want to add this.
        if not info.active.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add inactive domain_type {domain_type[0]} on {domain_name}",
            )
            return transition_domain

        # Are we updating data that already exists,
        # or are we adding new data in its place?
        federal_agency_exists = (
            transition_domain.organization_type is not None
            and transition_domain.federal_agency.strip() != ""
        )
        federal_type_exists = (
            transition_domain.federal_type is not None
            and transition_domain.federal_type.strip() != ""
        )

        # If we get two records, then we know it is federal.
        # needs to be lowercase for federal type
        is_federal = domain_type.count() == 2
        if is_federal:
            new_federal_type = domain_type[1].strip()
            transition_domain.organization_type = new_organization_type
            transition_domain.federal_type = new_federal_type
        else:
            transition_domain.organization_type = new_organization_type
            transition_domain.federal_type = None

        # Logs if we either added to this property,
        # or modified it.
        self._add_or_change_message(
            EnumFilenames.DOMAIN_ADHOC,
            "federal_agency",
            transition_domain.federal_agency,
            domain_name,
            federal_agency_exists,
        )

        self._add_or_change_message(
            EnumFilenames.DOMAIN_ADHOC,
            "federal_type",
            transition_domain.federal_type,
            domain_name,
            federal_type_exists,
        )

        return transition_domain

    def parse_org_data(self, domain_name, transition_domain: TransitionDomain) -> TransitionDomain:
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        org_info = self.get_org_info(domain_name)
        if org_info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.ORGANIZATION_ADHOC,
                LogCode.INFO,
                f"Could not add organization_name on {domain_name}, no data exists.",
            )
            return transition_domain

        desired_property_exists = (
            transition_domain.organization_name is not None
            and transition_domain.organization_name.strip() != ""
        )

        transition_domain.organization_name = org_info.orgname

        # Logs if we either added to this property,
        # or modified it.
        self._add_or_change_message(
            EnumFilenames.ORGANIZATION_ADHOC,
            "organization_name",
            transition_domain.organization_name,
            domain_name,
            desired_property_exists,
        )

        return transition_domain

    def _add_or_change_message(
        self, file_type, var_name, changed_value, domain_name, is_update=False
    ):
        """Creates a log instance when a property
        is successfully changed on a given TransitionDomain."""
        if not is_update:
            self.parse_logs.create_log_item(
                file_type,
                LogCode.DEBUG,
                f"Added {file_type} as '{var_name}' on {domain_name}",
            )
        else:
            self.parse_logs.create_log_item(
                file_type,
                LogCode.INFO,
                f"Updated existing {var_name} to '{changed_value}' on {domain_name}",
            )

    # Property getters, i.e. orgid or domaintypeid
    def get_org_info(self, domain_name) -> OrganizationAdhoc:
        domain_info = self.get_domain_data(domain_name)
        org_id = domain_info.orgid
        return self.get_organization_adhoc(org_id)

    def get_domain_type_info(self, domain_name) -> DomainTypeAdhoc:
        domain_info = self.get_domain_data(domain_name)
        type_id = domain_info.domaintypeid
        return self.get_domain_adhoc(type_id)

    def get_agency_info(self, domain_name) -> AgencyAdhoc:
        domain_info = self.get_domain_data(domain_name)
        type_id = domain_info.orgid
        return self.get_domain_adhoc(type_id)
    
    def get_authority_info(self, domain_name):
        domain_info = self.get_domain_data(domain_name)
        type_id = domain_info.authorityid
        return self.get_authority_adhoc(type_id)

    # Object getters, i.e. DomainAdditionalData or OrganizationAdhoc
    def get_domain_data(self, desired_id) -> DomainAdditionalData:
        return self.get_object_by_id(EnumFilenames.DOMAIN_ADDITIONAL, desired_id)

    def get_organization_adhoc(self, desired_id) -> OrganizationAdhoc:
        """Grabs adhoc information for organizations. Returns an organization
        adhoc object.
        """
        return self.get_object_by_id(EnumFilenames.ORGANIZATION_ADHOC, desired_id)

    def get_domain_adhoc(self, desired_id) -> DomainTypeAdhoc:
        """"""
        return self.get_object_by_id(EnumFilenames.DOMAIN_ADHOC, desired_id)

    def get_agency_adhoc(self, desired_id) -> AgencyAdhoc:
        """"""
        return self.get_object_by_id(EnumFilenames.AGENCY_ADHOC, desired_id)
    
    def get_authority_adhoc(self, desired_id) -> AuthorityAdhoc:
        """"""
        return self.get_object_by_id(EnumFilenames.AUTHORITY_ADHOC, desired_id)

    def get_object_by_id(self, file_type: EnumFilenames, desired_id):
        """Returns a field in a dictionary based off the type and id.

        vars:
            file_type: (constant) EnumFilenames -> Which data file to target.
            An example would be `EnumFilenames.DOMAIN_ADHOC`.

            desired_id: str -> Which id you want to search on. 
            An example would be `"12"` or `"igorville.gov"`
        
        Explanation:
            Each data file has an associated type (file_type) for tracking purposes.

            Each file_type is a dictionary which 
            contains a dictionary of row[id_field]: object.

            In practice, this would look like:

            EnumFilenames.AUTHORITY_ADHOC: { 
                "1": AuthorityAdhoc(...),
                "2": AuthorityAdhoc(...),
                ...
            }
            
            desired_id will then specify which id to grab. If we wanted "1",
            then this function will return the value of id "1".
            So, `AuthorityAdhoc(...)`
        """
        # Grabs a dict associated with the file_type.
        # For example, EnumFilenames.DOMAIN_ADDITIONAL.
        desired_type = self.domain_object.file_data.get(file_type)
        if desired_type is None:
            self.parse_logs.create_log_item(
                file_type, LogCode.ERROR, f"Type {file_type} does not exist"
            )
            return None

        # Grab the value given an Id within that file_type dict. 
        # For example, "igorville.gov".
        obj = desired_type.get(desired_id)
        if obj is None:
            self.parse_logs.create_log_item(
                file_type, LogCode.ERROR, f"Id {desired_id} does not exist"
            )

        return obj
