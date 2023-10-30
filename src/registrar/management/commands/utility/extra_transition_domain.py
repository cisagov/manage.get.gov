""""""
import csv
from dataclasses import dataclass
import glob
import re
import logging

import os
from typing import List
from .epp_data_containers import (
    AgencyAdhoc,
    DomainAdditionalData,
    DomainTypeAdhoc,
    OrganizationAdhoc,
    AuthorityAdhoc,
    EnumFilenames,
)

logger = logging.getLogger(__name__)


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

    data: dict -> The returned data. Intended to be used with data_type
    to cross-reference.

    """

    def __init__(
        self,
        filename: str,
        regex: re.Pattern,
        data_type: type,
        id_field: str,
    ):
        self.regex = regex
        self.data_type = data_type
        self.id_field = id_field
        self.data = {}
        self.filename = filename
        self.could_infer = False

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

        date = match.group(1)
        filename_without_date = match.group(2)

        # Can the supplied self.regex do a match on the filename?
        can_infer = filename_without_date == default_file_name
        if not can_infer:
            return (self.filename, False)

        # If so, note that and return the inferred name
        full_filename = date + "." + filename_without_date
        return (full_filename, can_infer)


class ExtraTransitionDomain:
    """Helper class to aid in storing TransitionDomain data spread across
    multiple files."""
    filenames = EnumFilenames
    #strip_date_regex = re.compile(r"\d+\.(.+)")
    strip_date_regex = re.compile(r"(?:.*\/)?(\d+)\.(.+)")

    def __init__(
        self,
        agency_adhoc_filename=filenames.AGENCY_ADHOC.value[1],
        domain_additional_filename=filenames.DOMAIN_ADDITIONAL.value[1],
        domain_adhoc_filename=filenames.DOMAIN_ADHOC.value[1],
        organization_adhoc_filename=filenames.ORGANIZATION_ADHOC.value[1],
        authority_adhoc_filename=filenames.AUTHORITY_ADHOC.value[1],
        directory="migrationdata",
        seperator="|",
    ):
        # Add a slash if the last character isn't one
        if directory and directory[-1] != "/":
            directory += "/"
        self.directory = directory
        self.seperator = seperator

        self.all_files = glob.glob(f"{directory}*")
        # Create a set with filenames as keys for quick lookup
        self.all_files_set = {os.path.basename(file) for file in self.all_files}
        self.file_data = {
            # (filename, default_url): metadata about the desired file
            self.filenames.AGENCY_ADHOC: PatternMap(
                agency_adhoc_filename, self.strip_date_regex, AgencyAdhoc, "agencyid"
            ),
            self.filenames.DOMAIN_ADDITIONAL: PatternMap(
                domain_additional_filename,
                self.strip_date_regex,
                DomainAdditionalData,
                "domainname",
            ),
            self.filenames.DOMAIN_ADHOC: PatternMap(
                domain_adhoc_filename,
                self.strip_date_regex,
                DomainTypeAdhoc,
                "domaintypeid",
            ),
            self.filenames.ORGANIZATION_ADHOC: PatternMap(
                organization_adhoc_filename,
                self.strip_date_regex,
                OrganizationAdhoc,
                "orgid",
            ),
            self.filenames.AUTHORITY_ADHOC: PatternMap(
                authority_adhoc_filename,
                self.strip_date_regex,
                AuthorityAdhoc,
                "authorityid",
            ),
        }

    def parse_all_files(self, infer_filenames=True):
        """Clears all preexisting data then parses each related CSV file.

        overwrite_existing_data: bool -> Determines if we should clear
        file_data.data if it already exists
        """
        self.clear_file_data()
        for name, value in self.file_data.items():
            filename = f"{value.filename}"

            if filename in self.all_files_set:
                _file = f"{self.directory}{value.filename}"
                value.data = self._read_csv_file(
                    _file,
                    self.seperator,
                    value.data_type,
                    value.id_field,
                )
            else:
                if not infer_filenames:
                    logger.error(f"Could not find file: {filename}")
                    continue
                
                logger.warning(
                    "Attempting to infer filename" 
                    f" for file: {filename}."
                )
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
                    value.data = self._read_csv_file(
                        _file,
                        self.seperator,
                        value.data_type,
                        value.id_field,
                    )
                    continue
                # Log if we can't find the desired file
                logger.error(f"Could not find file: {filename}")

    def clear_file_data(self):
        for item in self.file_data.values():
            file_type: PatternMap = item
            file_type.data = {}

    def _read_csv_file(self, file, seperator, dataclass_type, id_field):
        with open(file, "r", encoding="utf-8-sig") as requested_file:
            reader = csv.DictReader(requested_file, delimiter=seperator)
            dict_data = {row[id_field]: dataclass_type(**row) for row in reader}
            logger.debug(f"it is finally here {dict_data}")
            return dict_data
