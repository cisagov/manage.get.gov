"""Load domains from registry export."""

import csv
import logging
import sys

from django.core.management.base import BaseCommand

from registrar.models import Domain

logger = logging.getLogger(__name__)


def _domain_dict_reader(file_object, **kwargs):
    """A csv DictReader with the correct field names for escrow_domains data.

    All keyword arguments are sent on to the DictReader function call.
    """
    # field names are from escrow_manifests without "f"
    return csv.DictReader(
        file_object,
        fieldnames=[
            "Name",
            "Roid",
            "IdnTableId",
            "Registrant",
            "ClID",
            "CrRr",
            "CrID",
            "CrDate",
            "UpRr",
            "UpID",
            "UpDate",
            "ExDate",
            "TrDate",
        ],
        **kwargs,
    )


class Command(BaseCommand):
    help = "Load domain data from a delimited text file on stdin."

    def add_arguments(self, parser):
        parser.add_argument("--sep", default="|", help="Separator character for data file")

    def handle(self, *args, **options):
        separator_character = options.get("sep")
        reader = _domain_dict_reader(sys.stdin, delimiter=separator_character)
        # accumulate model objects so we can `bulk_create` them all at once.
        domains = []
        for row in reader:
            name = row["Name"].lower()  # we typically use lowercase domains
            domains.append(Domain(name=name))
        logger.info("Creating %d new domains", len(domains))
        Domain.objects.bulk_create(domains)
