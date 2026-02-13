""""""

import csv
from dataclasses import dataclass
from datetime import datetime
import io
import glob
import re
import logging

import os
import sys
from typing import Dict, List
from django.core.paginator import Paginator
from registrar.utility.enums import LogCode
from registrar.models.transition_domain import TransitionDomain
from registrar.management.commands.utility.load_organization_error import (
    LoadOrganizationError,
    LoadOrganizationErrorCodes,
)

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
from .terminal_helper import TerminalColors, TerminalHelper

logger = logging.getLogger(__name__)


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
        self.logs = {}

    class LogItem:
        """Used for storing data about logger information."""

        def __init__(self, file_type, code, message, domain_name):
            self.file_type = file_type
            self.code = code
            self.message = message
            self.domain_name = domain_name

    def add_log(self, file_type, code, message, domain_name):
        """Adds a log item to self.logs

        file_type -> Which enum to associate with,
        ex. EnumFilenames.DOMAIN_ADHOC

        code -> Log severity or other metadata, ex. LogCode.ERROR

        message -> Message to display

        domain_name -> Name of the domain, i.e. "igorville.gov"
        """
        log = self.LogItem(file_type, code, message, domain_name)
        dict_name = (file_type, domain_name)
        self._add_to_log_list(dict_name, log)

    def create_log_item(
        self,
        file_type,
        code,
        message,
        domain_name=None,
        add_to_list=True,
        minimal_logging=True,
    ):
        """Creates and returns an LogItem object.

        add_to_list: bool -> If enabled, add it to the logs array.
        """
        log = self.LogItem(file_type, code, message, domain_name)
        if not add_to_list:
            return log

        dict_name = (file_type, domain_name)
        self._add_to_log_list(dict_name, log)

        restrict_type = []
        if minimal_logging:
            restrict_type = [LogCode.INFO, LogCode.WARNING]
        TerminalHelper.print_conditional(
            log.code not in restrict_type,
            log.message,
            log.code,
        )

        return log

    def _add_to_log_list(self, log_name, log):
        if log_name not in self.logs:
            self.logs[log_name] = [log]
        else:
            self.logs[log_name].append(log)

    def display_all_logs(self):
        """Logs every LogItem contained in this object"""
        for parent_log in self.logs:
            for child_log in parent_log:
                TerminalHelper.print_conditional(True, child_log.message, child_log.severity)

    def display_logs_by_domain_name(self, domain_name, restrict_type=LogCode.DEFAULT):
        """Displays all logs of a given domain_name.
        Will log with the correct severity depending on code.

        domain_name: str -> The domain to target, such as "igorville.gov"

        restrict_type: LogCode -> Determines if only errors of a certain
        type should be displayed, such as LogCode.ERROR.
        """
        for file_type in EnumFilenames:
            domain_logs = self.get_logs(file_type, domain_name)
            if domain_logs is None:
                return None

            for log in domain_logs:
                TerminalHelper.print_conditional(restrict_type != log.code, log.message, log.code)

    def get_logs(self, file_type, domain_name):
        """Grabs the logs associated with
        a particular file_type and domain_name"""
        log_name = (file_type, domain_name)
        return self.logs.get(log_name)


class LoadExtraTransitionDomain:
    """Grabs additional data for TransitionDomains."""

    def __init__(self, options: TransitionDomainArguments):
        # Globally stores event logs and organizes them
        self.parse_logs = FileTransitionLog()
        self.debug = options.debug
        # Reads and parses migration files
        self.parsed_data_container = ExtraTransitionDomain(options)
        self.parsed_data_container.parse_all_files(options.infer_filenames)

    def update_transition_domain_models(self):
        """Updates TransitionDomain objects based off the file content
        given in self.parsed_data_container"""
        valid_transition_domains = TransitionDomain.objects.filter(processed=False)
        if not valid_transition_domains.exists():
            raise ValueError("No updatable TransitionDomain objects exist.")

        updated_transition_domains = []
        failed_transition_domains = []
        for transition_domain in valid_transition_domains:
            domain_name = transition_domain.domain_name
            updated_transition_domain = transition_domain
            try:
                # STEP 1: Parse organization data
                updated_transition_domain = self.parse_org_data(domain_name, transition_domain)

                # STEP 2: Parse domain type data
                updated_transition_domain = self.parse_domain_type_data(domain_name, transition_domain)

                # STEP 3: Parse agency data
                updated_transition_domain = self.parse_agency_data(domain_name, transition_domain)

                # STEP 4: Parse so data
                updated_transition_domain = self.parse_authority_data(domain_name, transition_domain)

                # STEP 5: Parse creation and expiration data
                updated_transition_domain = self.parse_creation_expiration_data(domain_name, transition_domain)

                updated_transition_domains.append(updated_transition_domain)
                logger.info(f"{TerminalColors.OKCYAN}" f"Successfully updated {domain_name}" f"{TerminalColors.ENDC}")

            # If we run into an exception on this domain,
            # Just skip over it and log that it happened.
            # Q: Should we just throw an exception?
            except Exception as err:
                logger.debug(err)
                logger.error(
                    f"{TerminalColors.FAIL}"
                    f"Exception encountered on {domain_name}. Could not update."
                    f"{TerminalColors.ENDC}"
                )
                failed_transition_domains.append(domain_name)

        updated_fields = [
            "organization_name",
            "generic_org_type",
            "federal_type",
            "federal_agency",
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "phone",
            "epp_creation_date",
            "epp_expiration_date",
        ]

        batch_size = 1000
        # Create a Paginator object. Bulk_update on the full dataset
        # is too memory intensive for our current app config, so we can chunk this data instead.
        paginator = Paginator(updated_transition_domains, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            TransitionDomain.objects.bulk_update(page.object_list, updated_fields)

        failed_count = len(failed_transition_domains)
        if failed_count == 0:
            if self.debug:
                for domain in updated_transition_domains:
                    logger.debug(domain.display_transition_domain())
            logger.info(
                f"""{TerminalColors.OKGREEN}
                ============= FINISHED ===============
                Updated {len(updated_transition_domains)} transition domain entries
                {TerminalColors.ENDC}
                """
            )
        else:
            # TODO - update
            TerminalHelper.print_conditional(
                self.debug,
                f"{TerminalHelper.array_as_string(updated_transition_domains)}",
            )
            logger.error(
                f"""{TerminalColors.FAIL}
                ============= FINISHED WITH ERRORS ===============
                Updated {len(updated_transition_domains)} transition domain entries,
                Failed to update {failed_count} transition domain entries:
                {[domain for domain in failed_transition_domains]}
                {TerminalColors.ENDC}
                """
            )

        # DATA INTEGRITY CHECK
        # Make sure every Transition Domain got updated
        total_transition_domains = len(updated_transition_domains)
        total_updates_made = TransitionDomain.objects.filter(processed=False).count()
        if total_transition_domains != total_updates_made:
            # noqa here for line length
            logger.error(
                f"""{TerminalColors.FAIL}
                            WARNING: something went wrong processing domain information data.
                            
                            Total Transition Domains expecting a data update: {total_transition_domains}
                            Total updates made: {total_updates_made}

                            ^ These totals should match, but they don't.  This
                            error should never occur, but could indicate
                            corrupt data.  Please check logs to diagnose.

                            ----- TERMINATING ----
                            """
            )  # noqa
            sys.exit()

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
                "Could not add epp_creation_date and epp_expiration_date " f"on {domain_name}, no data exists.",
                domain_name,
                not self.debug,
            )
            return transition_domain

        creation_exists = transition_domain.epp_creation_date is not None
        expiration_exists = transition_domain.epp_expiration_date is not None

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

    def log_add_or_changed_values(self, file_type, values_to_check, domain_name):
        for field_name, value in values_to_check:
            str_exists = value is not None and value.strip() != ""
            # Logs if we either added to this property,
            # or modified it.
            self._add_or_change_message(
                file_type,
                field_name,
                value,
                domain_name,
                str_exists,
            )

    def parse_authority_data(self, domain_name, transition_domain) -> TransitionDomain:
        """Grabs senior_offical data from the parsed files and associates it
        with a transition_domain object, then returns that object."""
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        info = self.get_authority_info(domain_name)
        if info is None:
            self.parse_logs.create_log_item(
                EnumFilenames.AGENCY_ADHOC,
                LogCode.ERROR,
                f"Could not add senior_official on {domain_name}, no data exists.",
                domain_name,
                not self.debug,
            )
            return transition_domain

        transition_domain.first_name = info.firstname
        transition_domain.middle_name = info.middlename
        transition_domain.last_name = info.lastname
        transition_domain.email = info.email
        transition_domain.phone = info.phonenumber

        changed_fields = [
            ("first_name", transition_domain.first_name),
            ("middle_name", transition_domain.middle_name),
            ("last_name", transition_domain.last_name),
            ("email", transition_domain.email),
            ("phone", transition_domain.phone),
        ]
        self.log_add_or_changed_values(EnumFilenames.AUTHORITY_ADHOC, changed_fields, domain_name)

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
                not self.debug,
            )
            return transition_domain

        agency_exists = transition_domain.federal_agency is not None and transition_domain.federal_agency.strip() != ""

        if not isinstance(info.active, str) or not info.active.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add inactive agency {info.agencyname} on {domain_name}",
                domain_name,
                not self.debug,
            )
            return transition_domain

        if not isinstance(info.isfederal, str) or not info.isfederal.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.INFO,
                f"Adding non-federal agency {info.agencyname} on {domain_name}",
                domain_name,
                not self.debug,
            )

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

    def parse_domain_type_data(self, domain_name, transition_domain: TransitionDomain) -> TransitionDomain:
        """Grabs generic_org_type and federal_type from the parsed files
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
                not self.debug,
            )
            return transition_domain

        # This data is stored as follows: FEDERAL - Judicial
        # For all other records, it is stored as so: Interstate
        # We can infer if it is federal or not based on this fact.
        domain_type = []
        if isinstance(info.domaintype, str):
            domain_type = info.domaintype.split("-")
        domain_type_length = len(domain_type)
        if domain_type_length < 1 or domain_type_length > 2:
            raise ValueError("Found invalid data on DOMAIN_ADHOC")

        # Then, just grab the organization type.
        new_generic_org_type = domain_type[0].strip()

        # Check if this domain_type is active or not.
        # If not, we don't want to add this.
        if not isinstance(info.active, str) or not info.active.lower() == "y":
            self.parse_logs.create_log_item(
                EnumFilenames.DOMAIN_ADHOC,
                LogCode.ERROR,
                f"Could not add inactive domain_type {domain_type[0]} on {domain_name}",
                domain_name,
                not self.debug,
            )
            return transition_domain

        # Are we updating data that already exists,
        # or are we adding new data in its place?
        generic_org_type_exists = (
            transition_domain.generic_org_type is not None and transition_domain.generic_org_type.strip() != ""
        )
        federal_type_exists = (
            transition_domain.federal_type is not None and transition_domain.federal_type.strip() != ""
        )

        # If we get two records, then we know it is federal.
        # needs to be lowercase for federal type
        is_federal = domain_type_length == 2
        if is_federal:
            new_federal_type = domain_type[1].strip()
            transition_domain.generic_org_type = new_generic_org_type
            transition_domain.federal_type = new_federal_type
        else:
            transition_domain.generic_org_type = new_generic_org_type
            transition_domain.federal_type = None

        # Logs if we either added to this property,
        # or modified it.
        self._add_or_change_message(
            EnumFilenames.DOMAIN_ADHOC,
            "generic_org_type",
            transition_domain.generic_org_type,
            domain_name,
            generic_org_type_exists,
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
                not self.debug,
            )
            return transition_domain

        desired_property_exists = (
            transition_domain.organization_name is not None and transition_domain.organization_name.strip() != ""
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

    def _add_or_change_message(self, file_type, var_name, changed_value, domain_name, is_update=False):
        """Creates a log instance when a property
        is successfully changed on a given TransitionDomain."""
        if not is_update:
            self.parse_logs.create_log_item(
                file_type,
                LogCode.INFO,
                f"Added {var_name} as '{changed_value}' on {domain_name}",
                domain_name,
                not self.debug,
            )
        else:
            self.parse_logs.create_log_item(
                file_type,
                LogCode.WARNING,
                f"Updated existing {var_name} to '{changed_value}' on {domain_name}",
                domain_name,
                not self.debug,
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

        # The agency record is within the authority adhoc
        authority_id = domain_info.authorityid
        authority = self.get_authority_adhoc(authority_id)

        type_id = None
        if authority is not None:
            type_id = authority.agencyid

        return self.get_agency_adhoc(type_id)

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

    # TODO - renamed / needs a return section
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
                file_type,
                LogCode.ERROR,
                f"Type {file_type} does not exist",
            )
            return None

        # Grab the value given an Id within that file_type dict.
        # For example, "igorville.gov".
        obj = desired_type.data.get(desired_id)
        if obj is None:
            self.parse_logs.create_log_item(
                file_type,
                LogCode.ERROR,
                f"Id {desired_id} does not exist for {file_type.value[0]}",
            )
        return obj


# TODO - change name
@dataclass
class FileDataHolder:
    """Helper class that holds data about a requested file.

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
    """  # noqa

    def __init__(
        self,
        filename: str,
        regex: re.Pattern,
        data_type: type,
        id_field: str,
    ):
        # Metadata #
        # = Filename inference metadata =#
        self.regex = regex
        self.could_infer = False

        # = "data" object metadata =#
        # == Where the data is sourced from ==#
        self.filename = filename

        # == What type the data is ==#
        self.data_type = data_type

        # == What the id should be in the holding dict ==#
        # TODO - rename to id_field_name
        self.id_field = id_field

        # Object data #
        self.data: Dict[str, type] = {}

    # This is used ONLY for development purposes. This behaviour
    # is controlled by the --infer_filename flag which is defaulted
    # to false. The purpose of this check is to speed up development,
    # but it cannot be used by the enduser
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


class OrganizationDataLoader:
    """Saves organization data onto Transition Domains. Handles file parsing."""

    def __init__(self, options: TransitionDomainArguments):
        self.debug = options.debug

        # We want to data from the domain_additional file and the organization_adhoc file
        options.pattern_map_params = [
            (
                EnumFilenames.DOMAIN_ADDITIONAL,
                options.domain_additional_filename,
                DomainAdditionalData,
                "domainname",
            ),
            (
                EnumFilenames.ORGANIZATION_ADHOC,
                options.organization_adhoc_filename,
                OrganizationAdhoc,
                "orgid",
            ),
        ]

        # Reads and parses organization data
        self.parsed_data = ExtraTransitionDomain(options)

        # options.infer_filenames will always be false when not SETTING.DEBUG
        self.parsed_data.parse_all_files(options.infer_filenames)

        self.tds_to_update: List[TransitionDomain] = []

    def update_organization_data_for_all(self):
        """Updates org address data for valid TransitionDomains"""
        all_transition_domains = TransitionDomain.objects.all()
        if len(all_transition_domains) == 0:
            raise LoadOrganizationError(code=LoadOrganizationErrorCodes.EMPTY_TRANSITION_DOMAIN_TABLE)

        self.prepare_transition_domains(all_transition_domains)

        logger.info(f"{TerminalColors.MAGENTA}" "Beginning mass TransitionDomain update..." f"{TerminalColors.ENDC}")
        self.bulk_update_transition_domains(self.tds_to_update)

        return self.tds_to_update

    def prepare_transition_domains(self, transition_domains):
        """Parses org data for each transition domain,
        then appends it to the tds_to_update list"""
        for item in transition_domains:
            updated = self.parse_org_data(item.domain_name, item)
            self.tds_to_update.append(updated)
            if self.debug:
                logger.info(
                    f"""{TerminalColors.OKCYAN}
                    Successfully updated:
                    {item.display_transition_domain()}
                    {TerminalColors.ENDC}"""
                )

        if self.debug:
            logger.info(f"Updating the following: {[item for item in self.tds_to_update]}")

        logger.info(
            f"""{TerminalColors.MAGENTA}
            Ready to update {len(self.tds_to_update)} TransitionDomains.
            {TerminalColors.ENDC}"""
        )

    def bulk_update_transition_domains(self, update_list):
        changed_fields = [
            "address_line",
            "city",
            "state_territory",
            "zipcode",
        ]

        batch_size = 1000
        # Create a Paginator object. Bulk_update on the full dataset
        # is too memory intensive for our current app config, so we can chunk this data instead.
        paginator = Paginator(update_list, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            TransitionDomain.objects.bulk_update(page.object_list, changed_fields)

        if self.debug:
            logger.info(f"Updated the following: {[item for item in self.tds_to_update]}")

        logger.info(
            f"{TerminalColors.OKGREEN}" f"Updated {len(self.tds_to_update)} TransitionDomains." f"{TerminalColors.ENDC}"
        )

    def parse_org_data(self, domain_name, transition_domain: TransitionDomain) -> TransitionDomain:
        """Grabs organization_name from the parsed files and associates it
        with a transition_domain object, then  updates that transition domain object and returns it"""
        if not isinstance(transition_domain, TransitionDomain):
            raise ValueError("Not a valid object, must be TransitionDomain")

        org_info = self.get_org_info(domain_name)
        if org_info is None:
            logger.error(f"Could not add organization data on {domain_name}, no data exists.")
            return transition_domain

        # Add street info
        transition_domain.address_line = org_info.orgstreet
        transition_domain.city = org_info.orgcity
        transition_domain.state_territory = org_info.orgstate
        transition_domain.zipcode = org_info.orgzip

        if self.debug:
            # Log what happened to each field. The first value
            # is the field name that was updated, second is the value
            changed_fields = [
                ("address_line", transition_domain.address_line),
                ("city", transition_domain.city),
                ("state_territory", transition_domain.state_territory),
                ("zipcode", transition_domain.zipcode),
            ]
            self.log_add_or_changed_values(changed_fields, domain_name)

        return transition_domain

    def get_org_info(self, domain_name) -> OrganizationAdhoc | None:
        """Maps an id given in get_domain_data to a organization_adhoc
        record which has its corresponding definition"""
        # Get a row in the domain_additional file. The id is the domain_name.
        domain_additional_row = self.retrieve_row_by_id(EnumFilenames.DOMAIN_ADDITIONAL, domain_name)
        if domain_additional_row is None:
            return None

        # Get a row in the organization_adhoc file. The id is the orgid in domain_additional_row.
        org_row = self.retrieve_row_by_id(EnumFilenames.ORGANIZATION_ADHOC, domain_additional_row.orgid)
        return org_row

    def retrieve_row_by_id(self, file_type: EnumFilenames, desired_id):
        """Returns a field in a dictionary based off the type and id.

        vars:
            file_type: (constant) EnumFilenames -> Which data file to target.
            An example would be `EnumFilenames.DOMAIN_ADHOC`.

            desired_id: str -> Which id you want to search on.
            An example would be `"12"` or `"igorville.gov"`
        """
        # Grabs a dict associated with the file_type.
        # For example, EnumFilenames.DOMAIN_ADDITIONAL would map to
        # whatever data exists on the domain_additional file.
        desired_file = self.parsed_data.file_data.get(file_type)
        if desired_file is None:
            logger.error(f"Type {file_type} does not exist")
            return None

        # This is essentially a dictionary of rows.
        data_in_file = desired_file.data

        # Get a row in the given file, based on an id.
        # For instance, "igorville.gov" in domain_additional.
        row_in_file = data_in_file.get(desired_id)
        if row_in_file is None:
            logger.error(f"Id {desired_id} does not exist for {file_type.value[0]}")

        return row_in_file

    def log_add_or_changed_values(self, values_to_check, domain_name):
        """Iterates through a list of fields, and determines if we should log
        if the field was added or if the field was updated.

        A field is "updated" when it is not None or not "".
        A field is "created" when it is either of those things.


        """
        for field_name, value in values_to_check:
            str_exists = value is not None and value.strip() != ""
            # Logs if we either added to this property,
            # or modified it.
            self._add_or_change_message(
                field_name,
                value,
                domain_name,
                str_exists,
            )

    def _add_or_change_message(self, field_name, changed_value, domain_name, is_update=False):
        """Creates a log instance when a property
        is successfully changed on a given TransitionDomain."""
        if not is_update:
            logger.info(f"Added {field_name} as '{changed_value}' on {domain_name}")
        else:
            logger.warning(f"Updated existing {field_name} to '{changed_value}' on {domain_name}")


class ExtraTransitionDomain:
    """Helper class to aid in storing TransitionDomain data spread across
    multiple files."""

    strip_date_regex = re.compile(r"(?:.*\/)?(\d+)\.(.+)")

    def __init__(self, options: TransitionDomainArguments):
        # Add a slash if the last character isn't one
        if options.directory and options.directory[-1] != "/":
            options.directory += "/"
        self.directory = options.directory
        self.seperator = options.sep

        self.all_files = glob.glob(f"{self.directory}*")

        # Create a set with filenames as keys for quick lookup
        self.all_files_set = {os.path.basename(file) for file in self.all_files}

        # Used for a container of values at each filename.
        # Instead of tracking each in a seperate variable, we can declare
        # metadata about each file and associate it with an enum.
        # That way if we want the data located at the agency_adhoc file,
        # we can just call EnumFilenames.AGENCY_ADHOC.
        if options.pattern_map_params is None or options.pattern_map_params == []:
            options.pattern_map_params = [
                (
                    EnumFilenames.AGENCY_ADHOC,
                    options.agency_adhoc_filename,
                    AgencyAdhoc,
                    "agencyid",
                ),
                (
                    EnumFilenames.DOMAIN_ADDITIONAL,
                    options.domain_additional_filename,
                    DomainAdditionalData,
                    "domainname",
                ),
                (
                    EnumFilenames.DOMAIN_ESCROW,
                    options.domain_escrow_filename,
                    DomainEscrow,
                    "domainname",
                ),
                (
                    EnumFilenames.DOMAIN_ADHOC,
                    options.domain_adhoc_filename,
                    DomainTypeAdhoc,
                    "domaintypeid",
                ),
                (
                    EnumFilenames.ORGANIZATION_ADHOC,
                    options.organization_adhoc_filename,
                    OrganizationAdhoc,
                    "orgid",
                ),
                (
                    EnumFilenames.AUTHORITY_ADHOC,
                    options.authority_adhoc_filename,
                    AuthorityAdhoc,
                    "authorityid",
                ),
            ]

        self.file_data = self.populate_file_data(options.pattern_map_params)

    # TODO - revise comment
    def populate_file_data(self, pattern_map_params):
        """Populates the self.file_data field given a set
        of tuple params.

        pattern_map_params must adhere to this format:
            [
                (file_type, filename, data_type, id_field),
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
            EnumFilenames.AUTHORITY_ADHOC: FileDataHolder(
                authority_adhoc_filename,
                self.strip_date_regex,
                AuthorityAdhoc,
                "authorityid",
            ),
        """
        file_data = {}
        for file_type, filename, data_type, id_field in pattern_map_params:
            file_data[file_type] = FileDataHolder(
                filename,
                self.strip_date_regex,
                data_type,
                id_field,
            )
        return file_data

    def parse_all_files(self, infer_filenames=True):
        """Clears all preexisting data then parses each related CSV file.

        infer_filenames: bool -> Determines if we should try to
        infer the filename if a default is passed in
        """
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
                    raise FileNotFoundError(
                        f"{TerminalColors.FAIL}" f"Could not find file {filename} for {name}" f"{TerminalColors.ENDC}"
                    )

                # Infer filename logic #
                # This mode is used for
                # internal development use and testing only.
                # Rather than havingto manually define the
                # filename each time, we can infer what the filename
                # actually is.

                # Not intended for use outside of that, as it is better to assume
                # the end-user wants to be specific.
                logger.warning(f"Attempting to infer filename: {filename}")
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
                raise FileNotFoundError(
                    f"{TerminalColors.FAIL}" f"Could not find file {filename} for {name}" f"{TerminalColors.ENDC}"
                )

    def clear_file_data(self):
        for item in self.file_data.values():
            file_type: FileDataHolder = item
            file_type.data = {}

    def parse_csv_file(self, file, seperator, dataclass_type, id_field, is_domain_escrow=False):
        # Domain escrow is an edge case
        if is_domain_escrow:
            item_to_return = self._read_domain_escrow(file, seperator)
            return item_to_return
        else:
            item_to_return = self._read_csv_file(file, seperator, dataclass_type, id_field)
            return item_to_return

    # Domain escrow is an edgecase given that its structured differently data-wise.
    def _read_domain_escrow(self, file, seperator):
        dict_data = {}
        with open(file, "r", encoding="utf-8-sig") as requested_file:
            reader = csv.reader(requested_file, delimiter=seperator)
            for row in reader:
                domain_name = row[0]
                date_format = "%Y-%m-%dT%H:%M:%SZ"
                # TODO - add error handling
                creation_date = datetime.strptime(row[7], date_format)
                expiration_date = datetime.strptime(row[11], date_format)

                dict_data[domain_name] = DomainEscrow(domain_name, creation_date, expiration_date)
        return dict_data

    def _grab_row_id(self, row, id_field, file, dataclass_type):
        try:
            row_id = row[id_field]
        except KeyError as err:
            logger.error(
                f"{TerminalColors.FAIL}"
                "\n Key mismatch! Did you upload the wrong file?"
                f"\n File: {file}"
                f"\n Expected type: {dataclass_type}"
                f"{TerminalColors.ENDC}"
            )
            raise err
        else:
            return row_id

    def _read_csv_file(self, file, seperator, dataclass_type, id_field):
        dict_data = {}
        # Used when we encounter bad data
        updated_file_content = None
        with open(file, "r", encoding="utf-8-sig") as requested_file:
            reader = csv.DictReader(requested_file, delimiter=seperator)
            for row in reader:
                # Checks if we encounter any bad data.
                # If we do, we (non-destructively) clean the file
                if None in row:
                    logger.warning(
                        f"{TerminalColors.YELLOW}"
                        f"Found bad data in {file}. Attempting to clean."
                        f"{TerminalColors.ENDC}"
                    )
                    updated_file_content = self.replace_bad_seperators(file, f"{seperator}", ";badseperator;")
                    dict_data = {}
                    break

                row_id = self._grab_row_id(row, id_field, file, dataclass_type)

                # To maintain pairity with the load_transition_domain
                # script, we store this data in lowercase.
                if id_field == "domainname" and row_id is not None:
                    row_id = row_id.lower()
                dict_data[row_id] = dataclass_type(**row)

        # After we clean the data, try to parse it again
        if updated_file_content:
            logger.info(f"{TerminalColors.MAGENTA}" f"Retrying load for {file}" f"{TerminalColors.ENDC}")
            # Store the file locally rather than writing to the file.
            # This is to avoid potential data corruption.
            updated_file = io.StringIO(updated_file_content)
            reader = csv.DictReader(updated_file, delimiter=seperator)
            for row in reader:
                row_id = row[id_field]
                # If the key is still none, something
                # is wrong with the file.
                if None in row:
                    logger.error(
                        f"{TerminalColors.FAIL}" f"Corrupt data found for {row_id}. Skipping." f"{TerminalColors.ENDC}"
                    )
                    continue

                for key, value in row.items():
                    if value is not None and isinstance(value, str):
                        value = value.replace(";badseperator;", f" {seperator} ")
                    row[key] = value

                # To maintain pairity with the load_transition_domain
                # script, we store this data in lowercase.
                if id_field == "domainname" and row_id is not None:
                    row_id = row_id.lower()
                dict_data[row_id] = dataclass_type(**row)
        return dict_data

    def replace_bad_seperators(self, filename, delimiter, special_character):
        with open(filename, "r", encoding="utf-8-sig") as file:
            contents = file.read()

        new_content = re.sub(rf" \{delimiter} ", special_character, contents)
        return new_content
