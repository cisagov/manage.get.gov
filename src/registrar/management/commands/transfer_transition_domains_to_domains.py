"""Load domain invitations for existing domains and their contacts."""

import logging
import argparse

from django_fsm import TransitionNotAllowed  # type: ignore

from django.core.management import BaseCommand

from registrar.models import TransitionDomain
from registrar.models import Domain

logger = logging.getLogger(__name__)


class termColors:
    """Colors for terminal outputs
    (makes reading the logs WAY easier)"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BackgroundLightYellow = "\033[103m"


# ----------------------------------------
#  MAIN SCRIPT
# ----------------------------------------
class Command(BaseCommand):
    help = """Load data from transition domain tables
    into main domain tables."""

    def add_arguments(self, parser):
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse", default=0, help="Sets max number of entries to load"
        )

    def handle(  # noqa: C901
        self,
        **options,
    ):
        """Load the data files and create the DomainInvitations."""

        # grab command line arguments and store locally...
        debug_on = options.get("debug")
        debug_max_entries_to_parse = int(
            options.get("limitParse")
        )  # set to 0 to parse all entries

        self.print_debug_mode_statements(debug_on, debug_max_entries_to_parse)

        # domains to ADD
        to_create = []
        # domains we UPDATED
        updated_domain_entries = []
        # domains we SKIPPED
        skipped_domain_entries = []
        # if we are limiting our parse (for testing purposes, keep
        # track of total rows parsed)
        total_rows_parsed = 0

        logger.info(
            f"""{termColors.OKGREEN}
==========================
Beginning Data Transfer
==========================
{termColors.ENDC}"""
        )

        for transition_entry in TransitionDomain.objects.all():
            transition_domain_name = transition_entry.domain_name
            transition_domain_status = transition_entry.status

            # Check for existing domain entry
            try:
                # DEBUG:
                if debug_on:
                    logger.info(
                        f"""{termColors.WARNING}
Processing Transition Domain: {transition_domain_name}, {transition_domain_status}
{termColors.ENDC}"""
                    )

                # for existing entry, update the status to
                # the transition domain status
                existingEntry = Domain.objects.get(name=transition_domain_name)
                current_state = existingEntry.state

                # DEBUG:
                if debug_on:
                    logger.info(
                        f"""{termColors.WARNING}
    > Found existing domain entry for: {transition_domain_name}, {current_state}
    {termColors.ENDC}"""
                    )
                if transition_domain_status != current_state:
                    if (
                        transition_domain_status
                        == TransitionDomain.StatusChoices.ON_HOLD
                    ):
                        existingEntry.place_client_hold(ignoreEPP=True)
                    else:
                        existingEntry.revert_client_hold(ignoreEPP=True)
                    existingEntry.save()
                    updated_domain_entries.append(existingEntry)
                    # DEBUG:
                    if debug_on:
                        logger.info(
                            f"""{termColors.WARNING}
    >> Updated {transition_domain_name} state from
    '{current_state}' to '{existingEntry.state}{termColors.ENDC}'"""
                        )
            except Domain.DoesNotExist:
                # no matching entry, make one
                newEntry = Domain(
                    name=transition_domain_name, state=transition_domain_status
                )
                to_create.append(newEntry)

                # DEBUG:
                if debug_on:
                    logger.info(
                        f"{termColors.OKCYAN} Adding entry: {newEntry} {termColors.ENDC}"  # noqa
                    )
            except Domain.MultipleObjectsReturned:
                logger.info(
                    f"""
{termColors.FAIL}
!!! ERROR: duplicate entries exist in the
Domain table for domain:
{transition_domain_name}
----------TERMINATING----------"""
                )
                import sys

                sys.exit()
            except TransitionNotAllowed as err:
                skipped_domain_entries.append(transition_domain_name)
                logger.info(
                    f"""{termColors.FAIL}
Unable to change state for {transition_domain_name}
    TRANSITION NOT ALLOWED error message (internal):
    {err}
    ----------SKIPPING----------"""
                )

            # DEBUG:
            if debug_on or debug_max_entries_to_parse > 0:
                if (
                    total_rows_parsed > debug_max_entries_to_parse
                    and debug_max_entries_to_parse != 0
                ):
                    logger.info(
                        f"""{termColors.WARNING}
                        ----PARSE LIMIT REACHED.  HALTING PARSER.----
                        {termColors.ENDC}
                        """
                    )
                    break

        Domain.objects.bulk_create(to_create)

        total_new_entries = len(to_create)
        total_updated_domain_entries = len(updated_domain_entries)

        logger.info(
            f"""{termColors.OKGREEN}

============= FINISHED ===============
Created {total_new_entries} transition domain entries,
updated {total_updated_domain_entries} transition domain entries
{termColors.ENDC}
"""
        )
        if len(skipped_domain_entries) > 0:
            logger.info(
                f"""{termColors.FAIL}

============= SKIPPED DOMAINS (ERRORS) ===============
{skipped_domain_entries}
{termColors.ENDC}
"""
            )

        # DEBUG:
        if debug_on:
            logger.info(
                f"""{termColors.WARNING}

Created Domains:
{to_create}

Updated Domains:
{updated_domain_entries}

{termColors.ENDC}
"""
            )

    # ----------------------------------------
    # HELPER FUNCTIONS
    # ----------------------------------------

    def print_debug_mode_statements(self, debug_on, debug_max_entries_to_parse):
        if debug_on:
            logger.info(
                f"""{termColors.WARNING}
----------DEBUG MODE ON----------
Detailed print statements activated.
{termColors.ENDC}
"""
            )
        if debug_max_entries_to_parse > 0:
            logger.info(
                f"""{termColors.OKCYAN}
----------LIMITER ON----------
Data transfer will be limited to
{debug_max_entries_to_parse} entries.")
{termColors.ENDC}
"""
            )
