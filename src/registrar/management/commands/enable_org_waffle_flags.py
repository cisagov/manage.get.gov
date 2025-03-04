"""Enables org-related waffle flags"""

import logging
from waffle.decorators import flag_is_active
from waffle.models import get_waffle_flag_model
from django.core.management import BaseCommand
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the cat command on files from /tmp into the getgov directory."

    def handle(self, **options):
        # Check for each flag. This is essentially get_or_create, so we have a db reference.
        added_flags = [
            "organization_feature",
            "organization_requests",
            "organization_members"
        ]
        for flag_name in added_flags:
            # We call flag_is_active first to auto-create the flag in the db.
            flag_is_active(None, flag_name)
            flag = get_waffle_flag_model().get(flag_name)
            if not flag.everyone:
                logger.info(f"Setting everyone on flag {flag_name} to True.")
                flag.everyone = True
                flag.save()
