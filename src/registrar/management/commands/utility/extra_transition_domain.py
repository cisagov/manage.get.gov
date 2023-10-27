""""""
import csv
from dataclasses import dataclass
import glob
import re
import logging

import os
from typing import List
from epp_data_containers import (
    AgencyAdhoc,
    DomainAdditionalData,
    DomainTypeAdhoc,
    OrganizationAdhoc,
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
        data: dict = {},
    ):
        self.regex = regex
        self.data_type = data_type
        self.id_field = id_field
        self.data = data

        # returns (filename, inferred_successfully)
        _infer = self._infer_filename(self.regex, filename)
        self.filename = _infer[0]
        self.could_infer = _infer[1]

    def _infer_filename(self, regex: re.Pattern, default_file_name):
        if not isinstance(regex, re.Pattern):
            return (self.filename, False)

        match = regex.match(self.filename)
        if not match:
            return (self.filename, False)

        date = match.group(1)
        filename_without_date = match.group(2)

        can_infer = filename_without_date == default_file_name
        if not can_infer:
            return (self.filename, False)

        full_filename = date + filename_without_date
        return (full_filename, can_infer)


class ExtraTransitionDomain:
    filenames = EnumFilenames
    strip_date_regex = re.compile(r"\d+\.(.+)")

    def __init__(
        self,
        agency_adhoc_filename=filenames.AGENCY_ADHOC[1],
        domain_additional_filename=filenames.DOMAIN_ADDITIONAL[1],
        domain_adhoc_filename=filenames.DOMAIN_ADHOC[1],
        organization_adhoc_filename=filenames.ORGANIZATION_ADHOC[1],
        directory="migrationdata",
        seperator="|",
    ):
        self.directory = directory
        self.seperator = seperator
        self.all_files = glob.glob(f"{directory}/*")
        # Create a set with filenames as keys for quick lookup
        self.all_files_set = {os.path.basename(file) for file in self.all_files}

        self.csv_data = {
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
        }

    def parse_all_files(self, overwrite_existing_data=True):
        """Clears all preexisting data then parses each related CSV file.

        overwrite_existing_data: bool -> Determines if we should clear
        csv_data.data if it already exists
        """
        self.clear_csv_data()
        for item in self.csv_data:
            file_type: PatternMap = item.value
            filename = file_type.filename

            if filename in self.all_files_set:
                file_type.data = self._read_csv_file(
                    self.all_files_set[filename],
                    self.seperator,
                    file_type.data_type,
                    file_type.id_field,
                )
            else:
                # Log if we can't find the desired file
                logger.error(f"Could not find file: {filename}")

    def clear_csv_data(self):
        for item in self.csv_data:
            file_type: PatternMap = item.value
            file_type.data = {}

    def _read_csv_file(self, file, seperator, dataclass_type, id_field):
        with open(file, "r", encoding="utf-8") as requested_file:
            reader = csv.DictReader(requested_file, delimiter=seperator)
            return {row[id_field]: dataclass_type(**row) for row in reader}
