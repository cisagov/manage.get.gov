"""Load domain invitations for existing domains and their contacts."""

import logging
import argparse
import sys

from django_fsm import TransitionNotAllowed  # type: ignore

from django.core.management import BaseCommand

from registrar.models import TransitionDomain
from registrar.models import Domain
from registrar.models import DomainInvitation

logger = logging.getLogger(__name__)


class termColors:
    """Colors for terminal outputs
    (makes reading the logs WAY easier)"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    YELLOW = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BackgroundLightYellow = "\033[103m"


class Command(BaseCommand):
    help = """Load data from transition domain tables
    into main domain tables.  Also create domain invitation
    entries for every domain we ADD (but not for domains
    we UPDATE)"""

    def add_arguments(self, parser):
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse",
            default=0,
            help="Sets max number of entries to load, set to 0 to load all entries",
        )

    def print_debug_mode_statements(
        self, debug_on: bool, debug_max_entries_to_parse: int
    ):
        """Prints additional terminal statements to indicate if --debug
        or --limitParse are in use"""
        if debug_on:
            logger.info(
                f"""{termColors.OKCYAN}
                ----------DEBUG MODE ON----------
                Detailed print statements activated.
                {termColors.ENDC}
                """
            )
        if debug_max_entries_to_parse > 0:
            logger.info(
                f"""{termColors.OKCYAN}
                ----------LIMITER ON----------
                Parsing of entries will be limited to
                {debug_max_entries_to_parse} lines per file.")
                Detailed print statements activated.
                {termColors.ENDC}
                """
            )

    def handle(  # noqa: C901
        self,
        **options,
    ):
        """Parse entries in TransitionDomain table
        and create (or update) corresponding entries in the
        Domain and DomainInvitation tables."""

        # grab command line arguments and store locally...
        debug_on = options.get("debug")
        debug_max_entries_to_parse = int(
            options.get("limitParse")
        )  # set to 0 to parse all entries

        self.print_debug_mode_statements(debug_on, debug_max_entries_to_parse)

        # domains to ADD
        domains_to_create = []
        domain_invitations_to_create = []
        # domains we UPDATED
        updated_domain_entries = []
        # domains we SKIPPED
        skipped_domain_entries = []
        # domainInvitations we SKIPPED
        skipped_domain_invitations = []
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
            transition_domain_email = transition_entry.username

            # Check for existing domain entry
            try:
                # DEBUG:
                if debug_on:
                    logger.info(
                        f"""{termColors.OKCYAN}
                        Processing Transition Domain: {transition_domain_name}, {transition_domain_status}, {transition_domain_email}
                        {termColors.ENDC}"""  # noqa
                    )

                # for existing entry, update the status to
                # the transition domain status
                existingEntry = Domain.objects.get(name=transition_domain_name)
                current_state = existingEntry.state

                # DEBUG:
                if debug_on:
                    logger.info(
                        f"""{termColors.YELLOW}
                        > Found existing domain entry for: {transition_domain_name}, {current_state}
                        {termColors.ENDC}"""  # noqa
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
                            f"""{termColors.YELLOW}
                            >> Updated {transition_domain_name} state from
                            '{current_state}' to '{existingEntry.state}'
                            (no domain invitation entry added)
                            {termColors.ENDC}"""
                        )
            except Domain.DoesNotExist:
                already_in_to_create = next(
                    (x for x in domains_to_create if x.name == transition_domain_name),
                    None,
                )
                if already_in_to_create:
                    # DEBUG:
                    if debug_on:
                        logger.info(
                            f"""{termColors.YELLOW}
                            Duplicate Detected: {transition_domain_name}.
                            Cannot add duplicate entry for another username.
                            Violates Unique Key constraint.
                            {termColors.ENDC}"""
                        )
                else:
                    # no matching entry, make one
                    new_entry = Domain(
                        name=transition_domain_name, state=transition_domain_status
                    )
                    domains_to_create.append(new_entry)

                    if transition_domain_email:
                        new_domain_invitation = DomainInvitation(
                            email=transition_domain_email.lower(), domain=new_entry
                        )
                        domain_invitations_to_create.append(new_domain_invitation)
                    else:
                        logger.info(
                            f"{termColors.FAIL} ! No e-mail found for domain: {new_entry}"
                            f"(SKIPPED ADDING DOMAIN INVITATION){termColors.ENDC}"
                        )
                        skipped_domain_invitations.append(transition_domain_name)

                    # DEBUG:
                    if debug_on:
                        logger.info(
                            f"{termColors.OKCYAN} Adding domain AND domain invitation: {new_entry} {termColors.ENDC}"  # noqa
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
                    total_rows_parsed >= debug_max_entries_to_parse
                    and debug_max_entries_to_parse != 0
                ):
                    logger.info(
                        f"""{termColors.YELLOW}
                        ----PARSE LIMIT REACHED.  HALTING PARSER.----
                        {termColors.ENDC}
                        """
                    )
                    break

        Domain.objects.bulk_create(domains_to_create)
        DomainInvitation.objects.bulk_create(domain_invitations_to_create)

        total_new_entries = len(domains_to_create)
        total_updated_domain_entries = len(updated_domain_entries)
        total_domain_invitation_entries = len(domain_invitations_to_create)

        logger.info(
            f"""{termColors.OKGREEN}
            ============= FINISHED ===============
            Created {total_new_entries} transition domain entries,
            updated {total_updated_domain_entries} transition domain entries

            Created {total_domain_invitation_entries} domain invitation entries
            (NOTE: no invitations are SENT in this script)
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
        if len(skipped_domain_invitations) > 0:
            logger.info(
                f"""{termColors.FAIL}
                ============= SKIPPED DOMAIN INVITATIONS (ERRORS) ===============
                {skipped_domain_invitations}
                {termColors.ENDC}
                """
            )

        # DEBUG:
        if debug_on:
            logger.info(
                f"""{termColors.YELLOW}

                Created Domains:
                {domains_to_create}

                Updated Domains:
                {updated_domain_entries}

                {termColors.ENDC}
                """
            )
