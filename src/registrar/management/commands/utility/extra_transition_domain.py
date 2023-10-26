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
    AGENCY_ADHOC = "agency.adhoc.dotgov.txt"
    DOMAIN_ADDITIONAL = "domainadditionaldatalink.adhoc.dotgov.txt"
    DOMAIN_ADHOC = "domaintypes.adhoc.dotgov.txt"
    ORGANIZATION_ADHOC = "organization.adhoc.dotgov.txt"

@dataclass
class PatternMap():
    def __init__(self, filename, regex, datatype):
        self.filename = filename
        self.regex = regex
        self.datatype = datatype


class ExtraTransitionDomain():
    filenames = EnumFilenames
    strip_date_regex = re.compile(r'\d+\.(.+)')
    filename_pattern_mapping = {
        # filename - regex to use when encountered
        filenames.AGENCY_ADHOC: strip_date_regex,
        filenames.DOMAIN_ADDITIONAL: strip_date_regex,
        filenames.DOMAIN_ADHOC: strip_date_regex,
        filenames.ORGANIZATION_ADHOC: strip_date_regex
    }
    
    def __init__(self, 
        agency_adhoc_filename=filenames.AGENCY_ADHOC, 
        domain_additional_filename=filenames.DOMAIN_ADDITIONAL, 
        domain_adhoc_filename=filenames.DOMAIN_ADHOC,
        organization_adhoc_filename=filenames.ORGANIZATION_ADHOC,
        directory="migrationdata",
        seperator="|"
    ):
        self.directory = directory
        self.seperator = seperator
        self.all_files = glob.glob(f"{directory}/*")
        self.filename_dicts = []

        self.agency_adhoc: List[AgencyAdhoc] = []
        self.domain_additional: List[DomainAdditionalData] = []
        self.domain_adhoc: List[DomainTypeAdhoc] = []
        self.organization_adhoc: List[OrganizationAdhoc] = []

        # Generate filename dictionaries
        for filename, enum_pair in [
            (agency_adhoc_filename, self.filenames.AGENCY_ADHOC),
            (domain_additional_filename, self.filenames.DOMAIN_ADDITIONAL),
            (domain_adhoc_filename, self.filenames.DOMAIN_ADHOC),
            (organization_adhoc_filename, self.filenames.ORGANIZATION_ADHOC)
        ]:
            # Generates a dictionary that associates the enum type to
            # the requested filename, and checks if its the default type.
            self.filename_dicts.append(self._create_filename_dict(filename, enum_pair))

    def parse_all_files(self, seperator):
        for file in self.all_files:
            filename = os.path.basename(file)
            for item in self.filename_dicts:
                if filename == item.get("filename"):
                    match item.get("default_filename"):
                        case self.filenames.AGENCY_ADHOC:
                            self.agency_adhoc = self._read_csv_file(filename, seperator, AgencyAdhoc)
                        case self.filenames.DOMAIN_ADDITIONAL:
                            self.domain_additional = self._read_csv_file(filename, seperator, DomainAdditionalData)
                        case self.filenames.DOMAIN_ADHOC:
                            self.domain_adhoc = self._read_csv_file(filename, seperator, DomainTypeAdhoc)
                        case self.filenames.ORGANIZATION_ADHOC:
                            self.organization_adhoc = self._read_csv_file(filename, seperator, OrganizationAdhoc)
                        case _:
                            logger.warning("Could not find default mapping")
                    break

    def _read_csv_file(self, file, seperator, dataclass_type):
        with open(file, "r", encoding="utf-8") as requested_file:
            reader = csv.DictReader(requested_file, delimiter=seperator)
            return [dataclass_type(**row) for row in reader]
        

    def _create_filename_dict(self, filename, default_filename):
        regex = self.filename_pattern_mapping.get(filename)

        # returns (filename, inferred_successfully)
        infer = self._infer_filename(regex, filename)
        filename_dict = {
            "filename": infer[0],
            "default_filename": default_filename,
            "is_default": filename == default_filename,
            "could_infer": infer[1]
        }   
        return filename_dict
    
    def _infer_filename(self, regex, current_file_name):
        if regex is None:
            return (current_file_name, False)
        
        match = regex.match(current_file_name)

        if match is None:
            return (None, False)
        
        filename_without_date = match.group(1)
        return (match, filename_without_date == current_file_name)
