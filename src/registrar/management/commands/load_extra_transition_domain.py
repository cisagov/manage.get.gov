""""""
import csv
import glob
import re
import logging

import os
from typing import List
from enum import Enum
from django.core.management import BaseCommand
from .utility.extra_transition_domain import ExtraTransitionDomain


logger = logging.getLogger(__name__)

class EnumFilenames(Enum):
    AGENCY_ADHOC = "agency.adhoc.dotgov.txt"
    DOMAIN_ADDITIONAL = "domainadditionaldatalink.adhoc.dotgov.txt"
    DOMAIN_ADHOC = "domaintypes.adhoc.dotgov.txt"
    ORGANIZATION_ADHOC = "organization.adhoc.dotgov.txt"

class Command(BaseCommand):
    help = ""

    filenames = EnumFilenames

    strip_date_regex = re.compile(r'\d+\.(.+)')
    # While the prefix of these files typically includes the date,
    # the rest of them following a predefined pattern. Define this here,
    # and search for that to infer what is wanted.
    filename_pattern_mapping = {
        # filename - regex to use when encountered
        filenames.AGENCY_ADHOC: strip_date_regex,
        filenames.DOMAIN_ADDITIONAL: strip_date_regex,
        filenames.DOMAIN_ADHOC: strip_date_regex,
        filenames.ORGANIZATION_ADHOC: strip_date_regex
    }

    def add_arguments(self, parser):
        """Add filename arguments."""
        parser.add_argument(
            "--directory", 
            default="migrationdata", 
            help="Desired directory"
        )
        parser.add_argument(
            "--agency_adhoc_filename",
            default=self.filenames.AGENCY_ADHOC,
            help="Defines the filename for agency adhocs",
        )
        parser.add_argument(
            "--domain_additional_filename",
            default=self.filenames.DOMAIN_ADDITIONAL,
            help="Defines the filename for additional domain data",
        )
        parser.add_argument(
            "--domain_adhoc_filename",
            default=self.filenames.DOMAIN_ADHOC,
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument(
            "--organization_adhoc_filename",
            default=self.filenames.ORGANIZATION_ADHOC,
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument("--sep", default="|", help="Delimiter character")

    def handle(self, *args, **options):
        self.data = ExtraTransitionDomain(
            agency_adhoc_filename=options['agency_adhoc_filename'], 
            domain_additional_filename=options['domain_additional_filename'], 
            domain_adhoc_filename=options['domain_adhoc_filename'],
            organization_adhoc_filename=options['organization_adhoc_filename'],
            directory=options['directory'],
            seperator=options['sep']
        )
        

