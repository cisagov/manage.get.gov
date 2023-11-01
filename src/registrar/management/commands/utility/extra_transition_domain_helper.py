""""""
import csv
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import glob
import re
import logging

import os
from typing import List, Tuple

from registrar.models.transition_domain import TransitionDomain

from .epp_data_containers import (
    AgencyAdhoc,
    DomainAdditionalData,
    DomainEscrow,
    DomainTypeAdhoc,
    OrganizationAdhoc,
    AuthorityAdhoc,
    EnumFilenames,
)

from .transition_domain_arguments import TransitionDomainArguments

logger = logging.getLogger(__name__)


class LogCode(Enum):
    """Stores the desired log severity"""

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
            EnumFilenames.DOMAIN_ESCROW: [],
        }

    class LogItem:
        """Used for storing data about logger information."""

        def __init__(self, file_type, code, message, domain_name):
            self.file_type = file_type
            self.code = code
            self.message = message
            self.domain_name = domain_name

    def add_log(self, file_type, code, message, domain_name):
        """Adds a log item to self.logs

        file_type -> Which array to add to,
        ex. EnumFilenames.DOMAIN_ADHOC

        code -> Log severity or other metadata, ex. LogCode.ERROR

        message -> Message to display
        """
        self.logs[file_type].append(self.LogItem(file_type, code, message, domain_name))

    def create_log_item(
        self, file_type, code, message, domain_name=None, add_to_list=True
    ):
        """Creates and returns an LogItem object.

        add_to_list: bool -> If enabled, add it to the logs array.
        """
        log = self.LogItem(file_type, code, message, domain_name)
        if not add_to_list:
            return log
        else:
            self.logs[file_type].append(log)
        return log

    def display_all_logs(self):
        """Logs every LogItem contained in this object"""
        for file_type in self.logs:
            self.display_logs(file_type)

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
    
    def clear_logs(self):
        """Clears log information"""
        self.logs = {
            EnumFilenames.DOMAIN_ADHOC: [],
            EnumFilenames.AGENCY_ADHOC: [],
            EnumFilenames.ORGANIZATION_ADHOC: [],
            EnumFilenames.DOMAIN_ADDITIONAL: [],
            EnumFilenames.DOMAIN_ESCROW: [],
        }

    def get_logs(self, file_type):
        """Grabs the logs associated with 
        a particular file_type"""
        return self.logs.get(file_type)


class LoadExtraTransitionDomain:
    """Grabs additional data for TransitionDomains."""

    def __init__(self, options: TransitionDomainArguments):
        # Stores event logs and organizes them
        self.parse_logs = FileTransitionLog()

        arguments = options.args_extra_transition_domain()
        # Reads and parses migration files
        self.parsed_data_container = ExtraTransitionDomain(**arguments)
        self.parsed_data_container.parse_all_files()

    def create_update_model_logs(self, file_type):
        """Associates runtime logs to the file_type,
        such that we can determine where errors occured when
        updating a TransitionDomain model."""
        logs = self.parse_logs.get_logs(file_type)
        self.parsed_data_container.set_logs(file_type, logs)

    def update_transition_domain_models(self):
        """Updates TransitionDomain objects based off the file content
        given in self.parsed_data_container"""
        all_transition_domains = TransitionDomain.objects.all()
        if not all_transition_domains.exists():
            raise Exception("No TransitionDomain objects exist.")

        try:
            for transition_domain in all_transition_domains:
                domain_name = transition_domain.domain_name.upper()
                updated_transition_domain = transition_domain

                # STEP 1: Parse organization data
                updated_transition_domain = self.parse_org_data(
                    domain_name, transition_domain
                )
                # Store the event logs
                self.create_update_model_logs(EnumFilenames.ORGANIZATION_ADHOC)

                # STEP 2: Parse domain type data
                updated_transition_domain = self.parse_domain_type_data(
                    domain_name, transition_domain
                )
                # Store the event logs
                self.create_update_model_logs(EnumFilenames.DOMAIN_ADHOC)

                # STEP 3: Parse agency data
                updated_transition_domain = self.parse_agency_data(
                    domain_name, transition_domain
                )
                # Store the event logs
                self.create_update_model_logs(EnumFilenames.AGENCY_ADHOC)

                # STEP 4: Parse creation and expiration data
                updated_transition_domain = self.parse_creation_expiration_data(
                    domain_name, transition_domain
                )
                # Store the event logs
                self.create_update_model_logs(EnumFilenames.DOMAIN_ADHOC)

                updated_transition_domain.save()
                
                logger.info(f"Succesfully updated TransitionDomain {domain_name}")
                self.parse_logs.clear_logs()
        except Exception as err:
            logger.error("Could not update all TransitionDomain objects.")

            # Regardless of what occurred, log what happened.
            logger.info("======Printing log stack======")
            self.parse_logs.display_all_logs()

            raise err
        else:
            self.display_run_summary()

    def display_run_summary(self):
        """Prints information about this particular run.
        Organizes like data together.
        """
        container = self.parsed_data_container
        agency_adhoc = container.get_logs_for_type(EnumFilenames.AGENCY_ADHOC)
        authority_adhoc = container.get_logs_for_type(EnumFilenames.AUTHORITY_ADHOC)
        domain_additional = container.get_logs_for_type(EnumFilenames.DOMAIN_ADDITIONAL)
        domain_adhoc = container.get_logs_for_type(EnumFilenames.DOMAIN_ADHOC)
        domain_escrow = container.get_logs_for_type(EnumFilenames.DOMAIN_ESCROW)
        organization_adhoc = container.get_logs_for_type(EnumFilenames.ORGANIZATION_ADHOC)
        variable_data = []
        for file_type in self.parsed_data_container.file_data:
            # Grab all logs for 
            logs = self.parsed_data_container.get_logs_for_type(file_type)
            variable_data.append(logs)
        #agency_adhoc, authority_adhoc, domain_additional, domain_adhoc, domain_escrow, organization_adhoc = variable_data

    
    def parse_creation_expiration_data(self, domain_name, transition_domain):
        """Grabs expiration_date from the parsed files and associates it
        with a transition_domain object, then returns that object."""
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        info = self.get_domain_escrow_info(domain_name)
        if info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ESCROW,
                LogCode.ERROR,
                "Could not add epp_creation_date and epp_expiration_date " 
                f"on {domain_name}, no data exists.",
                domain_name,
            )
            return transition_domain

        creation_exists = (
            transition_domain.epp_creation_date is not None
        )
        expiration_exists = (
            transition_domain.epp_expiration_date is not None
        )

        transition_domain.epp_creation_date = info.creationdate
        transition_domain.epp_expiration_date = info.expirationdate

        # Logs if we either added to this property,
        # or modified it.
        self._add_or_change_message(
            EnumFilenames.DOMAIN_ESCROW,
            "epp_creation_date",
            transition_domain.epp_creation_date,
            domain_name,
            creation_exists,
        )
        self._add_or_change_message(
            EnumFilenames.DOMAIN_ESCROW,
            "epp_expiration_date",
            transition_domain.epp_expiration_date,
            domain_name,
            expiration_exists,
        )

        return transition_domain

    def parse_agency_data(self, domain_name, transition_domain) -> TransitionDomain:
        """Grabs federal_agency from the parsed files and associates it
        with a transition_domain object, then returns that object."""
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        info = self.get_agency_info(domain_name)
        if info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.AGENCY_ADHOC,
                LogCode.ERROR,
                f"Could not add federal_agency on {domain_name}, no data exists.",
                domain_name,
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
                domain_name,
            )
            return transition_domain

        if not info.isfederal.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add non-federal agency {info.agencyname} on {domain_name}",
                domain_name,
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
            agency_exists,
        )

        return transition_domain

    def parse_domain_type_data(
        self, domain_name, transition_domain: TransitionDomain
    ) -> TransitionDomain:
        """Grabs organization_type and federal_type from the parsed files
        and associates it with a transition_domain object, then returns that object."""
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        info = self.get_domain_type_info(domain_name)
        if info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add domain_type on {domain_name}, no data exists.",
                domain_name,
            )
            return transition_domain

        # This data is stored as follows: FEDERAL - Judicial
        # For all other records, it is stored as so: Interstate
        # We can infer if it is federal or not based on this fact.
        domain_type = info.domaintype.split("-")
        domain_type_length = len(domain_type)
        if domain_type_length < 1 or domain_type_length > 2:
            raise ValueError("Found invalid data on DOMAIN_ADHOC")

        # Then, just grab the organization type.
        new_organization_type = domain_type[0].strip()

        # Check if this domain_type is active or not.
        # If not, we don't want to add this.
        if not info.active.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add inactive domain_type {domain_type[0]} on {domain_name}",
                domain_name,
            )
            return transition_domain

        # Are we updating data that already exists,
        # or are we adding new data in its place?
        organization_type_exists = (
            transition_domain.organization_type is not None
            and transition_domain.organization_type.strip() != ""
        )
        federal_type_exists = (
            transition_domain.federal_type is not None
            and transition_domain.federal_type.strip() != ""
        )

        # If we get two records, then we know it is federal.
        # needs to be lowercase for federal type
        is_federal = domain_type_length == 2
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
            "organization_type",
            transition_domain.organization_type,
            domain_name,
            organization_type_exists,
        )

        self._add_or_change_message(
            EnumFilenames.DOMAIN_ADHOC,
            "federal_type",
            transition_domain.federal_type,
            domain_name,
            federal_type_exists,
        )

        return transition_domain

    def parse_org_data(
        self, domain_name, transition_domain: TransitionDomain
    ) -> TransitionDomain:
        """Grabs organization_name from the parsed files and associates it
        with a transition_domain object, then returns that object."""
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        org_info = self.get_org_info(domain_name)
        if org_info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.ORGANIZATION_ADHOC,
                LogCode.ERROR,
                f"Could not add organization_name on {domain_name}, no data exists.",
                domain_name,
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
                LogCode.INFO,
                f"Added {var_name} as '{changed_value}' on {domain_name}",
                domain_name,
            )
        else:
            self.parse_logs.create_log_item(
                file_type,
                LogCode.WARNING,
                f"Updated existing {var_name} to '{changed_value}' on {domain_name}",
                domain_name,
            )

    # Property getters, i.e. orgid or domaintypeid
    def get_org_info(self, domain_name) -> OrganizationAdhoc:
        """Maps an id given in get_domain_data to a organization_adhoc
        record which has its corresponding definition"""
        domain_info = self.get_domain_data(domain_name)
        if domain_info is None:
            return None
        org_id = domain_info.orgid
        return self.get_organization_adhoc(org_id)

    def get_domain_type_info(self, domain_name) -> DomainTypeAdhoc:
        """Maps an id given in get_domain_data to a domain_type_adhoc
        record which has its corresponding definition"""
        domain_info = self.get_domain_data(domain_name)
        if domain_info is None:
            return None
        type_id = domain_info.domaintypeid
        return self.get_domain_adhoc(type_id)

    def get_agency_info(self, domain_name) -> AgencyAdhoc:
        """Maps an id given in get_domain_data to a agency_adhoc
        record which has its corresponding definition"""
        domain_info = self.get_domain_data(domain_name)
        if domain_info is None:
            return None
        type_id = domain_info.orgid
        return self.get_domain_adhoc(type_id)

    def get_authority_info(self, domain_name):
        """Maps an id given in get_domain_data to a authority_adhoc
        record which has its corresponding definition"""
        domain_info = self.get_domain_data(domain_name)
        if domain_info is None:
            return None
        type_id = domain_info.authorityid
        return self.get_authority_adhoc(type_id)
    
    def get_domain_escrow_info(self, domain_name):
        domain_info = self.get_domain_data(domain_name)
        if domain_info is None:
            return None
        type_id = domain_info.domainname
        return self.get_domain_escrow(type_id)
    
    # Object getters, i.e. DomainAdditionalData or OrganizationAdhoc
    def get_domain_data(self, desired_id) -> DomainAdditionalData:
        """Grabs a corresponding row within the DOMAIN_ADDITIONAL file,
        based off a desired_id"""
        return self.get_object_by_id(EnumFilenames.DOMAIN_ADDITIONAL, desired_id)

    def get_organization_adhoc(self, desired_id) -> OrganizationAdhoc:
        """Grabs a corresponding row within the ORGANIZATION_ADHOC file,
        based off a desired_id"""
        return self.get_object_by_id(EnumFilenames.ORGANIZATION_ADHOC, desired_id)

    def get_domain_adhoc(self, desired_id) -> DomainTypeAdhoc:
        """Grabs a corresponding row within the DOMAIN_ADHOC file,
        based off a desired_id"""
        return self.get_object_by_id(EnumFilenames.DOMAIN_ADHOC, desired_id)

    def get_agency_adhoc(self, desired_id) -> AgencyAdhoc:
        """Grabs a corresponding row within the AGENCY_ADHOC file,
        based off a desired_id"""
        return self.get_object_by_id(EnumFilenames.AGENCY_ADHOC, desired_id)

    def get_authority_adhoc(self, desired_id) -> AuthorityAdhoc:
        """Grabs a corresponding row within the AUTHORITY_ADHOC file,
        based off a desired_id"""
        return self.get_object_by_id(EnumFilenames.AUTHORITY_ADHOC, desired_id)
    
    def get_domain_escrow(self, desired_id) -> DomainEscrow:
        """Grabs a corresponding row within the DOMAIN_ESCROW file,
        based off a desired_id"""
        return self.get_object_by_id(EnumFilenames.DOMAIN_ESCROW, desired_id)

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
        desired_type = self.parsed_data_container.file_data.get(file_type)
        if desired_type is None:
            self.parse_logs.create_log_item(
                file_type, LogCode.ERROR, f"Type {file_type} does not exist"
            )
            return None

        # Grab the value given an Id within that file_type dict.
        # For example, "igorville.gov".
        obj = desired_type.data.get(desired_id)
        if obj is None:
            self.parse_logs.create_log_item(
                file_type, LogCode.ERROR, f"Id {desired_id} does not exist"
            )
        return obj


@dataclass
class PatternMap:
    """Helper class that holds data and metadata about a requested file.

    filename: str -> The desired filename to target. If no filename is given,
    it is assumed that you are passing in a filename pattern and it will look
    for a filename that matches the given postfix you pass in.

    regex: re.Pattern -> Defines what regex you want to use when inferring
    filenames. If none, no matching occurs.

    data_type: type -> Metadata about the desired type for data.

    id_field: str -> Defines which field should act as the id in data.
    This is necessary as we store lists of "data_type" in ExtraTransitionDomain as follows:
        {
            id_field: data_type(...),
            id_field: data_type(...),
            ...
        }

    """

    def __init__(
        self,
        filename: str,
        regex: re.Pattern,
        data_type: type,
        id_field: str,
    ):
        # Metadata #
        ## Filename inference metadata ##
        self.regex = regex
        self.could_infer = False

        ## "data" object metadata ##
        ### Where the data is sourced from ###
        self.filename = filename

        ### What type the data is ###
        self.data_type = data_type

        ### What the id should be in the holding dict ###
        self.id_field = id_field

        # Object data #
        self.data = {}
        self.logs = {}

    def try_infer_filename(self, current_file_name, default_file_name):
        """Tries to match a given filename to a regex,
        then uses that match to generate the filename."""
        # returns (filename, inferred_successfully)
        return self._infer_filename(self.regex, current_file_name, default_file_name)

    def _infer_filename(self, regex: re.Pattern, matched_file_name, default_file_name):
        if not isinstance(regex, re.Pattern):
            return (self.filename, False)

        match = regex.match(matched_file_name)

        if not match:
            return (self.filename, False)

        total_groups = len(match.groups())

        # If no matches exist or if we have too many
        # matches, then we shouldn't infer
        if total_groups == 0 or total_groups > 2:
            return (self.filename, False)
        
        # If only one match is returned,
        # it means that our default matches our request
        if total_groups == 1:
            return (self.filename, True)
        
        # Otherwise, if two are returned, then
        # its likely the pattern we want
        date = match.group(1)
        filename_without_date = match.group(2)

        # After stripping out the date, 
        # do the two filenames match?
        can_infer = filename_without_date == default_file_name
        if not can_infer:
            return (self.filename, False)

        # If they do, recreate the filename and return it
        full_filename = date + "." + filename_without_date
        return (full_filename, can_infer)


class ExtraTransitionDomain:
    """Helper class to aid in storing TransitionDomain data spread across
    multiple files."""

    strip_date_regex = re.compile(r"(?:.*\/)?(\d+)\.(.+)")

    def __init__(
        self,
        agency_adhoc_filename=EnumFilenames.AGENCY_ADHOC.value[1],
        domain_additional_filename=EnumFilenames.DOMAIN_ADDITIONAL.value[1],
        domain_escrow_filename=EnumFilenames.DOMAIN_ESCROW.value[1],
        domain_adhoc_filename=EnumFilenames.DOMAIN_ADHOC.value[1],
        organization_adhoc_filename=EnumFilenames.ORGANIZATION_ADHOC.value[1],
        authority_adhoc_filename=EnumFilenames.AUTHORITY_ADHOC.value[1],
        directory="migrationdata",
        sep="|",
    ):
        # Add a slash if the last character isn't one
        if directory and directory[-1] != "/":
            directory += "/"
        self.directory = directory
        self.seperator = sep

        self.all_files = glob.glob(f"{directory}*")

        # Create a set with filenames as keys for quick lookup
        self.all_files_set = {os.path.basename(file) for file in self.all_files}

        # Used for a container of values at each filename.
        # Instead of tracking each in a seperate variable, we can declare
        # metadata about each file and associate it with an enum.
        # That way if we want the data located at the agency_adhoc file,
        # we can just call EnumFilenames.AGENCY_ADHOC.
        pattern_map_params = [
            (
                EnumFilenames.AGENCY_ADHOC,
                agency_adhoc_filename,
                AgencyAdhoc,
                "agencyid",
            ),
            (
                EnumFilenames.DOMAIN_ADDITIONAL,
                domain_additional_filename,
                DomainAdditionalData,
                "domainname",
            ),
            (
                EnumFilenames.DOMAIN_ESCROW,
                domain_escrow_filename,
                DomainEscrow,
                "domainname",
            ),
            (
                EnumFilenames.DOMAIN_ADHOC,
                domain_adhoc_filename,
                DomainTypeAdhoc,
                "domaintypeid",
            ),
            (
                EnumFilenames.ORGANIZATION_ADHOC,
                organization_adhoc_filename,
                OrganizationAdhoc,
                "orgid",
            ),
            (
                EnumFilenames.AUTHORITY_ADHOC,
                authority_adhoc_filename,
                AuthorityAdhoc,
                "authorityid",
            ),
        ]
        self.file_data = self.populate_file_data(pattern_map_params)

    def populate_file_data(
        self, pattern_map_params: List[Tuple[EnumFilenames, str, type, str]]
    ):
        """Populates the self.file_data field given a set
        of tuple params.

        pattern_map_params must adhere to this format:
            [
                (field_type, filename, data_type, id_field),
            ]

        vars:
            file_type (EnumFilenames) -> The name of the dictionary.
            Defined as a value on EnumFilenames, such as
            EnumFilenames.AGENCY_ADHOC

            filename (str) -> The filepath of the given
            "file_type", such as migrationdata/test123.txt

            data_type (type) -> The type of data to be read
            at the location of the filename. For instance,
            each row of test123.txt may return data of type AgencyAdhoc

            id_field (str) -> Given the "data_type" of each row,
            this specifies what the "id" of that row is.
            For example, "agencyid". This is used so we can
            store each record in a dictionary rather than
            a list of values.

        return example:
            EnumFilenames.AUTHORITY_ADHOC: PatternMap(
                authority_adhoc_filename,
                self.strip_date_regex,
                AuthorityAdhoc,
                "authorityid",
            ),
        """
        file_data = {}
        for file_type, filename, data_type, id_field in pattern_map_params:
            file_data[file_type] = PatternMap(
                filename,
                self.strip_date_regex,
                data_type,
                id_field,
            )
        return file_data

    def parse_all_files(self, infer_filenames=True):
        """Clears all preexisting data then parses each related CSV file.

        overwrite_existing_data: bool -> Determines if we should clear
        file_data.data if it already exists
        """
        self.clear_file_data()
        for name, value in self.file_data.items():
            is_domain_escrow = name == EnumFilenames.DOMAIN_ESCROW
            filename = f"{value.filename}"
            if filename in self.all_files_set:
                _file = f"{self.directory}{value.filename}"
                value.data = self.parse_csv_file(
                    _file,
                    self.seperator,
                    value.data_type,
                    value.id_field,
                    is_domain_escrow,
                )
            else:
                if not infer_filenames:
                    logger.error(f"Could not find file: {filename}")
                    continue
                
                # Infer filename logic #
                # This mode is used for development and testing only. Rather than having
                # to manually define the filename each time, we can infer what the filename
                # actually is. 

                # Not intended for use outside of that, as it is better to assume
                # the end-user wants to be specific.
                logger.warning("Attempting to infer filename" f" for file: {filename}.")
                for filename in self.all_files:
                    default_name = name.value[1]
                    match = value.try_infer_filename(filename, default_name)
                    filename = match[0]
                    can_infer = match[1]
                    if can_infer:
                        break

                if filename in self.all_files_set:
                    logger.info(f"Infer success. Found file {filename}")
                    _file = f"{self.directory}{filename}"
                    value.data = self.parse_csv_file(
                        _file,
                        self.seperator,
                        value.data_type,
                        value.id_field,
                        is_domain_escrow,
                    )
                    continue
                # Log if we can't find the desired file
                logger.error(f"Could not find file: {filename}")

    def clear_file_data(self):
        for item in self.file_data.values():
            file_type: PatternMap = item
            file_type.data = {}

    def parse_csv_file(
        self,
        file_type,
        file,
        seperator,
        dataclass_type,
        id_field,
        is_domain_escrow=False
    ):
        # Domain escrow is an edge case
        if is_domain_escrow:
            item_to_return = self._read_domain_escrow(
                file_type,
                file,
                seperator
            )
            return item_to_return
        else:
            item_to_return = self._read_csv_file(
                file_type,
                file,
                seperator,
                dataclass_type,
                id_field
            )
            return item_to_return

    # Domain escrow is an edgecase given that its structured differently data-wise.
    def _read_domain_escrow(self, file_type, file, seperator):
        dict_data = {}
        with open(file, "r", encoding="utf-8-sig") as requested_file:
            reader = csv.reader(requested_file, delimiter=seperator)
            for row in reader:
                domain_name = row[0]
                date_format = "%Y-%m-%dT%H:%M:%SZ"
                # TODO - add error handling
                creation_date = datetime.strptime(row[7], date_format)
                expiration_date = datetime.strptime(row[11], date_format)

                dict_data[domain_name] = DomainEscrow(
                    domain_name, creation_date, expiration_date
                )

                # Given this row_id, create a default log object.
                # So that we can track logs on it later.
                self.set_log(file_type, domain_name, [])
        return dict_data

    def _read_csv_file(self, file_type, file, seperator, dataclass_type, id_field):
        with open(file, "r", encoding="utf-8-sig") as requested_file:
            reader = csv.DictReader(requested_file, delimiter=seperator)
            """
            for row in reader:
                print({key: type(key) for key in row.keys()})  # print out the keys and their types
                test = {row[id_field]: dataclass_type(**row)}
            """
            dict_data = {}
            for row in reader:
                if None in row:
                    print("Skipping row with None key")
                    # for key, value in row.items():
                    # print(f"key: {key} value: {value}")
                    continue
                row_id = row[id_field]
                dict_data[row_id] = dataclass_type(**row)

                # Given this row_id, create a default log object.
                # So that we can track logs on it later.
                self.set_log(file_type, row_id, [])
            # dict_data = {row[id_field]: dataclass_type(**row) for row in reader}
            return dict_data

    # Logging logic #
    def get_logs_for_type(self, file_type):
        """Returns all logs for the given file_type"""
        return self.file_data.get(file_type).logs
    
    def get_log(self, file_type, item_id):
        """Returns a log of a particular id"""
        logs = self.get_logs_for_type(file_type)
        return logs.get(item_id)

    def set_logs_for_type(self, file_type, logs):
        """Sets all logs for a given file_type"""
        self.file_data[file_type] = logs

    def set_log(self, file_type, item_id, log):
        """Creates a single log item under a given file_type"""
        self.file_data.get(file_type)[item_id] = log
