""""""
import csv
from dataclasses import dataclass
import glob
import re
import logging

import os
from typing import List
from enum import Enum
from epp_data_containers import AgencyAdhoc, DomainAdditionalData, DomainTypeAdhoc, OrganizationAdhoc

logger = logging.getLogger(__name__)

class EnumFilenames(Enum):
    """Returns a tuple mapping for (filetype, default_file_name). 
    
    For instance, AGENCY_ADHOC = ("agency_adhoc", "agency.adhoc.dotgov.txt")
    """
    AGENCY_ADHOC = ("agency_adhoc", "agency.adhoc.dotgov.txt")
    DOMAIN_ADDITIONAL = ("domain_additional", "domainadditionaldatalink.adhoc.dotgov.txt")
    DOMAIN_ADHOC = ("domain_adhoc", "domaintypes.adhoc.dotgov.txt")
    ORGANIZATION_ADHOC = ("organization_adhoc", "organization.adhoc.dotgov.txt")

@dataclass
class PatternMap():

    def __init__(self, filename: str, regex, data_type, data=[]):
        self.regex = regex
        self.data_type = data_type
        self.data = data

        # returns (filename, inferred_successfully)
        _infer = self._infer_filename(self.regex, filename)
        self.filename = _infer[0]
        self.could_infer = _infer[1]
    

    def _infer_filename(self, regex, default_file_name):
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

class ExtraTransitionDomain():
    filenames = EnumFilenames
    strip_date_regex = re.compile(r'\d+\.(.+)')
    
    def __init__(self, 
        agency_adhoc_filename=filenames.AGENCY_ADHOC[1],
        domain_additional_filename=filenames.DOMAIN_ADDITIONAL[1],
        domain_adhoc_filename=filenames.DOMAIN_ADHOC[1],
        organization_adhoc_filename=filenames.ORGANIZATION_ADHOC[1],
        directory="migrationdata",
        seperator="|"
    ):
        self.directory = directory
        self.seperator = seperator
        self.all_files = glob.glob(f"{directory}/*")
        # Create a set with filenames as keys for quick lookup
        self.all_files_set = {os.path.basename(file) for file in self.all_files}

        self.csv_data = {
            self.filenames.AGENCY_ADHOC: PatternMap(agency_adhoc_filename, self.strip_date_regex, AgencyAdhoc),
            self.filenames.DOMAIN_ADDITIONAL: PatternMap(domain_additional_filename, self.strip_date_regex, DomainAdditionalData),
            self.filenames.DOMAIN_ADHOC: PatternMap(domain_adhoc_filename, self.strip_date_regex, DomainTypeAdhoc),
            self.filenames.ORGANIZATION_ADHOC: PatternMap(organization_adhoc_filename, self.strip_date_regex, OrganizationAdhoc)
        }


    def parse_all_files(self):
        """Clears all preexisting data then parses each related CSV file"""
        self.clear_csv_data()
        for item in self.csv_data:
            file_type: PatternMap = item.value
            filename = file_type.filename

            if filename in self.all_files_set:
                file_type.data = self._read_csv_file(
                    self.all_files_set[filename], 
                    self.seperator, 
                    file_type.data_type
                )
            else:
                # Log if we can't find the desired file
                logger.warning(f"Could not find file: {filename}")

    
    def clear_csv_data(self):
        for item in self.csv_data:
            file_type: PatternMap = item.value
            file_type.data = []

    def _read_csv_file(self, file, seperator, dataclass_type):
        with open(file, "r", encoding="utf-8") as requested_file:
            reader = csv.DictReader(requested_file, delimiter=seperator)
            return [dataclass_type(**row) for row in reader]
        
