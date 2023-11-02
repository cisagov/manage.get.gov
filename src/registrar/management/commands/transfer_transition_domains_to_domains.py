import logging
import argparse
import sys

from django_fsm import TransitionNotAllowed  # type: ignore

from django.core.management import BaseCommand

from registrar.models import TransitionDomain
from registrar.models import Domain
from registrar.models import DomainInvitation

from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)
from registrar.models.domain_application import DomainApplication
from registrar.models.domain_information import DomainInformation
from registrar.models.user import User

logger = logging.getLogger(__name__)


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
        TerminalHelper.print_conditional(
            debug_on,
            f"""{TerminalColors.OKCYAN}
            ----------DEBUG MODE ON----------
            Detailed print statements activated.
            {TerminalColors.ENDC}
            """,
        )
        TerminalHelper.print_conditional(
            debug_max_entries_to_parse > 0,
            f"""{TerminalColors.OKCYAN}
            ----------LIMITER ON----------
            Parsing of entries will be limited to
            {debug_max_entries_to_parse} lines per file.")
            Detailed print statements activated.
            {TerminalColors.ENDC}
            """,
        )

    def update_domain_information(self, current: DomainInformation, target: DomainInformation, debug_on: bool) -> bool:
        updated = False

        fields_to_update = [
            'organization_type', 
            'federal_type', 
            'federal_agency',
            "organization_name"
        ] 
        defaults = {field: getattr(target, field) for field in fields_to_update}
        if current != target:
            current = target
            DomainInformation.objects.filter(domain=current.domain).update(**defaults)
            updated = True

        return updated

    def update_domain_status(
        self, transition_domain: TransitionDomain, target_domain: Domain, debug_on: bool
    ) -> bool:
        """Given a transition domain that matches an existing domain,
        updates the existing domain object with that status of
        the transition domain.
        Returns TRUE if an update was made.  FALSE if the states
        matched and no update was made"""

        transition_domain_status = transition_domain.status
        existing_status = target_domain.state
        if transition_domain_status != existing_status:
            if transition_domain_status == TransitionDomain.StatusChoices.ON_HOLD:
                target_domain.place_client_hold(ignoreEPP=True)
            else:
                target_domain.revert_client_hold(ignoreEPP=True)
            target_domain.save()

            # DEBUG:
            TerminalHelper.print_conditional(
                debug_on,
                f"""{TerminalColors.YELLOW}
                >> Updated {target_domain.name} state from
                '{existing_status}' to '{target_domain.state}'
                (no domain invitation entry added)
                {TerminalColors.ENDC}""",
            )
            return True
        return False

    def print_summary_of_findings(
        self,
        domains_to_create,
        updated_domain_entries,
        domain_invitations_to_create,
        skipped_domain_entries,
        domain_information_to_create,
        updated_domain_information,
        debug_on,
    ):
        """Prints to terminal a summary of findings from
        transferring transition domains to domains"""

        total_new_entries = len(domains_to_create)
        total_updated_domain_entries = len(updated_domain_entries)
        total_domain_invitation_entries = len(domain_invitations_to_create)

        total_new_domain_information_entries = len(domain_information_to_create)
        total_updated_domain_information_entries = len(updated_domain_information)

        logger.info(
            f"""{TerminalColors.OKGREEN}
            ============= FINISHED ===============
            Created {total_new_entries} domain entries,
            Updated {total_updated_domain_entries} domain entries

            Created {total_new_domain_information_entries} domain information entries,
            Updated {total_updated_domain_information_entries} domain information entries,

            Created {total_domain_invitation_entries} domain invitation entries
            (NOTE: no invitations are SENT in this script)
            {TerminalColors.ENDC}
            """
        )
        if len(skipped_domain_entries) > 0:
            logger.info(
                f"""{TerminalColors.FAIL}
                ============= SKIPPED DOMAINS (ERRORS) ===============
                {skipped_domain_entries}
                {TerminalColors.ENDC}
                """
            )

        # determine domainInvitations we SKIPPED
        skipped_domain_invitations = []
        for domain in domains_to_create:
            skipped_domain_invitations.append(domain)
        for domain_invite in domain_invitations_to_create:
            if domain_invite.domain in skipped_domain_invitations:
                skipped_domain_invitations.remove(domain_invite.domain)
        if len(skipped_domain_invitations) > 0:
            logger.info(
                f"""{TerminalColors.FAIL}
                ============= SKIPPED DOMAIN INVITATIONS (ERRORS) ===============
                {skipped_domain_invitations}
                {TerminalColors.ENDC}
                """
            )

        # DEBUG:
        TerminalHelper.print_conditional(
            debug_on,
            f"""{TerminalColors.YELLOW}
            ======= DEBUG OUTPUT =======
            Created Domains:
            {domains_to_create}

            Updated Domains:
            {updated_domain_entries}

            {TerminalColors.ENDC}
            """,
        )

    def try_add_domain_information(self):
        pass

    def try_add_domain_invitation(
        self, domain_email: str, associated_domain: Domain
    ) -> DomainInvitation | None:
        """If no domain invitation exists for the given domain and
        e-mail, create and return a new domain invitation object.
        If one already exists, or if the email is invalid, return NONE"""

        # this should never happen, but adding it just in case
        if associated_domain is None:
            logger.warning(
                f"""
                        {TerminalColors.FAIL}
                        !!! ERROR: Domain cannot be null for a
                        Domain Invitation object!

                        RECOMMENDATION:
                        Somehow, an empty domain object is
                        being passed to the subroutine in charge
                        of making domain invitations. Walk through
                        the code to see what is amiss.

                        ----------TERMINATING----------"""
            )
            sys.exit()

        # check that the given e-mail is valid
        if domain_email is not None and domain_email != "":
            # check that a domain invitation doesn't already
            # exist for this e-mail / Domain pair
            domain_email_already_in_domain_invites = DomainInvitation.objects.filter(
                email=domain_email.lower(), domain=associated_domain
            ).exists()
            if not domain_email_already_in_domain_invites:
                # Create new domain invitation
                new_domain_invitation = DomainInvitation(
                    email=domain_email.lower(), domain=associated_domain
                )
                return new_domain_invitation
        return None

    def handle(
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
        domain_information_to_create = []

        domain_invitations_to_create = []
        # domains we UPDATED
        updated_domain_entries = []
        updated_domain_information = []

        # domains we SKIPPED
        skipped_domain_entries = []
        skipped_domain_information_entries = []

        # if we are limiting our parse (for testing purposes, keep
        # track of total rows parsed)
        total_rows_parsed = 0

        logger.info(
            f"""{TerminalColors.OKGREEN}
            ==========================
            Beginning Data Transfer
            ==========================
            {TerminalColors.ENDC}"""
        )

        for transition_domain in TransitionDomain.objects.all():
            transition_domain_name = transition_domain.domain_name
            transition_domain_status = transition_domain.status
            transition_domain_email = transition_domain.username
            transition_domain_creation_date = transition_domain.epp_creation_date
            transition_domain_expiration_date = transition_domain.epp_expiration_date

            # DEBUG:
            TerminalHelper.print_conditional(
                debug_on,
                f"{TerminalColors.OKCYAN}"
                "Processing Transition Domain: " 
                f"{transition_domain_name}, {transition_domain_status}, {transition_domain_email}"
                f", {transition_domain_creation_date}, {transition_domain_expiration_date}"
                f"{TerminalColors.ENDC}",  # noqa
            )

            new_domain_invitation = None
            # Check for existing domain entry
            domain_exists = Domain.objects.filter(name=transition_domain_name).exists()
            if domain_exists:
                try:
                    # get the existing domain
                    domain_to_update = Domain.objects.get(name=transition_domain_name)
                    # DEBUG:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"""{TerminalColors.YELLOW}
                        > Found existing entry in Domain table for: {transition_domain_name}, {domain_to_update.state}
                        {TerminalColors.ENDC}""",  # noqa
                    )

                    # for existing entry, update the status to
                    # the transition domain status
                    update_made = self.update_domain_status(
                        transition_domain, domain_to_update, debug_on
                    )

                    domain_to_update.created_at = transition_domain_creation_date
                    domain_to_update.expiration_date = transition_domain_expiration_date
                    domain_to_update.save()

                    if update_made:
                        # keep track of updated domains for data analysis purposes
                        updated_domain_entries.append(transition_domain.domain_name)

                    # check if we need to add a domain invitation
                    # (eg. for a new user)
                    new_domain_invitation = self.try_add_domain_invitation(
                        transition_domain_email, domain_to_update
                    )

                except Domain.MultipleObjectsReturned:
                    # This exception was thrown once before during testing.
                    # While the circumstances that led to corrupt data in
                    # the domain table was a freak accident, and the possibility of it
                    # happening again is safe-guarded by a key constraint,
                    # better to keep an eye out for it since it would require
                    # immediate attention.
                    logger.warning(
                        f"""
                        {TerminalColors.FAIL}
                        !!! ERROR: duplicate entries already exist in the
                        Domain table for the following domain:
                        {transition_domain_name}

                        RECOMMENDATION:
                        This means the Domain table is corrupt.  Please
                        check the Domain table data as there should be a key
                        constraint which prevents duplicate entries.

                        ----------TERMINATING----------"""
                    )
                    sys.exit()
                except TransitionNotAllowed as err:
                    skipped_domain_entries.append(transition_domain_name)
                    logger.warning(
                        f"""{TerminalColors.FAIL}
                        Unable to change state for {transition_domain_name}

                        RECOMMENDATION:
                        This indicates there might have been changes to the
                        Domain model which were not accounted for in this
                        migration script.  Please check state change rules
                        in the Domain model and ensure we are following the
                        correct state transition pathways.

                        INTERNAL ERROR MESSAGE:
                        'TRANSITION NOT ALLOWED' exception
                        {err}
                        ----------SKIPPING----------"""
                    )
            else:
                # no entry was found in the domain table
                # for the given domain.  Create a new entry.

                # first see if we are already adding an entry for this domain.
                # The unique key constraint does not allow duplicate domain entries
                # even if there are different users.
                existing_domain_in_to_create = next(
                    (x for x in domains_to_create if x.name == transition_domain_name),
                    None,
                )
                if existing_domain_in_to_create is not None:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"""{TerminalColors.YELLOW}
                        Duplicate Detected: {transition_domain_name}.
                        Cannot add duplicate entry for another username.
                        Violates Unique Key constraint.

                        Checking for unique user e-mail for Domain Invitations...
                        {TerminalColors.ENDC}""",
                    )
                    new_domain_invitation = self.try_add_domain_invitation(
                        transition_domain_email, existing_domain_in_to_create
                    )
                else:
                    # no matching entry, make one
                    new_domain = Domain(
                        name=transition_domain_name,
                        state=transition_domain_status,
                        expiration_date=transition_domain_expiration_date,
                    )

                    
                    domains_to_create.append(new_domain)
                    # DEBUG:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"{TerminalColors.OKCYAN} Adding domain: {new_domain} {TerminalColors.ENDC}",  # noqa
                    )
                    new_domain_invitation = self.try_add_domain_invitation(
                        transition_domain_email, new_domain
                    )

            if new_domain_invitation is None:
                logger.info(
                    f"{TerminalColors.YELLOW} ! No new e-mail detected !"  # noqa
                    f"(SKIPPED ADDING DOMAIN INVITATION){TerminalColors.ENDC}"
                )
            else:
                # DEBUG:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"{TerminalColors.OKCYAN} Adding domain invitation: {new_domain_invitation} {TerminalColors.ENDC}",  # noqa
                )
                domain_invitations_to_create.append(new_domain_invitation)

            # Check parse limit and exit loop if parse limit has been reached
            if (
                debug_max_entries_to_parse > 0
                and total_rows_parsed >= debug_max_entries_to_parse
            ):
                logger.info(
                    f"""{TerminalColors.YELLOW}
                    ----PARSE LIMIT REACHED.  HALTING PARSER.----
                    {TerminalColors.ENDC}
                    """
                )
                break

        Domain.objects.bulk_create(domains_to_create)

        for transition_domain in TransitionDomain.objects.all():
            transition_domain_name = transition_domain.domain_name

            # Create associated domain information objects
            domain_data = Domain.objects.filter(name=transition_domain.domain_name)
            if not domain_data.exists():
                raise ValueError("No domain exists")
            
            domain = domain_data.get()

            org_type = transition_domain.organization_type
            fed_type = transition_domain.federal_type
            fed_agency = transition_domain.federal_agency



            valid_org_type = org_type in [choice_value for choice_value, _ in DomainApplication.OrganizationChoices.choices]
            valid_fed_type = fed_type in [choice_value for choice_value, _ in DomainApplication.BranchChoices.choices]
            valid_fed_agency = fed_agency in DomainApplication.AGENCIES

            default_creator, _ = User.objects.get_or_create(username="System")

            new_domain_info_data = {
                'domain': domain,
                'organization_name': transition_domain.organization_name,
                "creator": default_creator,
            }

            new_domain_info_data['federal_type'] = None
            for item in DomainApplication.BranchChoices.choices:
                print(f"it is this: {item}")
                name, _ = item
                if fed_type is not None and fed_type.lower() == name:
                    new_domain_info_data['federal_type'] = item
            
            new_domain_info_data['organization_type'] = org_type
            new_domain_info_data['federal_agency'] = fed_agency
            if valid_org_type:
                new_domain_info_data['organization_type'] = org_type
            else:
                logger.debug(f"No org type found on {domain.name}")

            if valid_fed_type:
                new_domain_info_data['federal_type'] = fed_type
            else:
                logger.debug(f"No federal type found on {domain.name}")

            if valid_fed_agency:
                new_domain_info_data['federal_agency'] = fed_agency
            else:
                logger.debug(f"No federal agency found on {domain.name}")

            new_domain_info = DomainInformation(**new_domain_info_data)

            domain_information_exists = DomainInformation.objects.filter(domain=domain).exists()
            
            if domain_information_exists:
                try:
                    # get the existing domain information object
                    domain_info_to_update = DomainInformation.objects.get(domain=domain)
                    # DEBUG:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"""{TerminalColors.YELLOW}
                        > Found existing entry in Domain Information table for: {transition_domain_name}
                        {TerminalColors.ENDC}""",  # noqa
                    )

                    # for existing entry, update the status to
                    # the transition domain status
                    update_made = self.update_domain_information(
                        domain_info_to_update, new_domain_info, debug_on
                    )
                    if update_made:
                        # keep track of updated domains for data analysis purposes
                        updated_domain_information.append(transition_domain.domain_name)
                except DomainInformation.MultipleObjectsReturned:
                    # This exception was thrown once before during testing.
                    # While the circumstances that led to corrupt data in
                    # the domain table was a freak accident, and the possibility of it
                    # happening again is safe-guarded by a key constraint,
                    # better to keep an eye out for it since it would require
                    # immediate attention.
                    logger.warning(
                        f"""
                        {TerminalColors.FAIL}
                        !!! ERROR: duplicate entries already exist in the
                        Domain Information table for the following domain:
                        {transition_domain_name}

                        RECOMMENDATION:
                        This means the Domain Information table is corrupt.  Please
                        check the Domain Information table data as there should be a key
                        constraint which prevents duplicate entries.

                        ----------TERMINATING----------"""
                    )
                    sys.exit()
            else:
                # no entry was found in the domain table
                # for the given domain.  Create a new entry.

                # first see if we are already adding an entry for this domain.
                # The unique key constraint does not allow duplicate domain entries
                # even if there are different users.
                existing_domain_info_in_to_create = next(
                    (x for x in domain_information_to_create if x.domain.name == transition_domain_name),
                    None,
                )
                if existing_domain_info_in_to_create is not None:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"""{TerminalColors.YELLOW}
                        Duplicate Detected: {transition_domain_name}.
                        Cannot add duplicate entry.
                        Violates Unique Key constraint.
                        {TerminalColors.ENDC}""",
                    )
                else:
                    # no matching entry, make one
                    domain_information_to_create.append(new_domain_info)
                    # DEBUG:
                    TerminalHelper.print_conditional(
                        debug_on,
                        f"{TerminalColors.OKCYAN} Adding domain information on: {new_domain_info.domain.name} {TerminalColors.ENDC}",  # noqa
                    )

        DomainInformation.objects.bulk_create(domain_information_to_create)

        DomainInvitation.objects.bulk_create(domain_invitations_to_create)

        self.print_summary_of_findings(
            domains_to_create,
            updated_domain_entries,
            domain_invitations_to_create,
            skipped_domain_entries,
            domain_information_to_create,
            updated_domain_information,
            debug_on,
        )
