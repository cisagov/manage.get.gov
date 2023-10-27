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
from .utility.epp_data_containers import AgencyAdhoc, DomainAdditionalData, DomainTypeAdhoc, OrganizationAdhoc, EnumFilenames

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ""
    filenames = EnumFilenames

    def add_arguments(self, parser):
        """Add filename arguments."""
        parser.add_argument(
            "--directory", 
            default="migrationdata", 
            help="Desired directory"
        )
        parser.add_argument(
            "--agency_adhoc_filename",
            default=self.filenames.AGENCY_ADHOC[1],
            help="Defines the filename for agency adhocs",
        )
        parser.add_argument(
            "--domain_additional_filename",
            default=self.filenames.DOMAIN_ADDITIONAL[1],
            help="Defines the filename for additional domain data",
        )
        parser.add_argument(
            "--domain_adhoc_filename",
            default=self.filenames.DOMAIN_ADHOC[1],
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument(
            "--organization_adhoc_filename",
            default=self.filenames.ORGANIZATION_ADHOC[1],
            help="Defines the filename for domain type adhocs",
        )
        parser.add_argument("--sep", default="|", help="Delimiter character")

    def handle(self, **options):
        try:
            self.domain_object = ExtraTransitionDomain(
                agency_adhoc_filename=options['agency_adhoc_filename'], 
                domain_additional_filename=options['domain_additional_filename'], 
                domain_adhoc_filename=options['domain_adhoc_filename'],
                organization_adhoc_filename=options['organization_adhoc_filename'],
                directory=options['directory'],
                seperator=options['sep']
            )
            self.domain_object.parse_all_files()
        except Exception as err:
            logger.error(f"Could not load additional data. Error: {err}")
        else:
            for transition_domain in TransitionDomain.objects.all():
                transition_domain.organization_type

    def get_organization_adhoc(self, desired_id):
        """Grabs adhoc information for organizations. Returns an organization
        dictionary
        
        returns: 
        { 
            "
        }
        """
        return self.get_object_by_id(self.filenames.ORGANIZATION_ADHOC, desired_id)
    
    def get_domain_adhoc(self, desired_id):
        """"""
        return self.get_object_by_id(self.filenames.DOMAIN_ADHOC, desired_id)
    
    def get_agency_adhoc(self, desired_id):
        """"""
        return self.get_object_by_id(self.filenames.AGENCY_ADHOC, desired_id)
    
    def get_object_by_id(self, file_type: EnumFilenames, desired_id):
        """"""
        desired_type = self.domain_object.csv_data.get(file_type)
        obj = desired_type.get(desired_id)
        return obj
