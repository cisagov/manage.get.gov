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
from registrar.models.contact import Contact
from registrar.models.domain_request import DomainRequest
from registrar.models.domain_information import DomainInformation
from registrar.models.user import User
from registrar.models.federal_agency import FederalAgency
from registrar.utility.constants import BranchChoices

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Load data from transition domain tables
    into main domain tables.  Also create domain invitation
    entries for every domain we ADD (but not for domains
    we UPDATE)"""

    # ======================================================
    # ===================== ARGUMENTS  =====================
    # ======================================================
    def add_arguments(self, parser):
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse",
            default=0,
            help="Sets max number of entries to load, set to 0 to load all entries",
        )

    # ======================================================
    # ===================== PRINTING  ======================
    # ======================================================
    def print_debug_mode_statements(self, debug_on: bool, debug_max_entries_to_parse: int):
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

    def parse_limit_reached(self, debug_max_entries_to_parse: bool, total_rows_parsed: int) -> bool:
        if debug_max_entries_to_parse > 0 and total_rows_parsed >= debug_max_entries_to_parse:
            logger.info(f"""{TerminalColors.YELLOW}
                ----PARSE LIMIT REACHED.  HALTING PARSER.----
                {TerminalColors.ENDC}
                """)
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

        logger.info(f"""{TerminalColors.OKGREEN}
            ============= FINISHED ===============
            Created {total_new_entries} domain entries,
            Updated {total_updated_domain_entries} domain entries

            Created {total_new_domain_information_entries} domain information entries,
            Updated {total_updated_domain_information_entries} domain information entries,

            Created {total_domain_invitation_entries} domain invitation entries
            (NOTE: no invitations are SENT in this script)
            {TerminalColors.ENDC}
            """)  # noqa
        if len(skipped_domain_entries) > 0:
            logger.info(f"""{TerminalColors.FAIL}
                ============= SKIPPED DOMAINS (ERRORS) ===============
                {skipped_domain_entries}
                {TerminalColors.ENDC}
                """)

        # determine domainInvitations we SKIPPED
        skipped_domain_invitations = []
        for domain in domains_to_create:
            skipped_domain_invitations.append(domain)
        for domain_invite in domain_invitations_to_create:
            if domain_invite.domain in skipped_domain_invitations:
                skipped_domain_invitations.remove(domain_invite.domain)
        if len(skipped_domain_invitations) > 0:
            logger.info(f"""{TerminalColors.FAIL}
                ============= SKIPPED DOMAIN INVITATIONS (ERRORS) ===============
                {skipped_domain_invitations}
                {TerminalColors.ENDC}
                """)

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

    # ======================================================
    # ===================    DOMAIN    =====================
    # ======================================================
    def update_or_create_domain(self, transition_domain: TransitionDomain, debug_on: bool):
        """Given a transition domain, either finds & updates an existing
        corresponding domain, or creates a new corresponding domain in
        the Domain table.

        Returns the corresponding Domain object and a boolean
        that is TRUE if that Domain was newly created.
        """

        # Create some local variables to make data tracing easier
        transition_domain_name = transition_domain.domain_name
        transition_domain_status = transition_domain.status
        transition_domain_creation_date = transition_domain.epp_creation_date
        transition_domain_expiration_date = transition_domain.epp_expiration_date

        domain_exists = Domain.objects.filter(name=transition_domain_name).exists()
        if domain_exists:
            try:
                # ----------------------- UPDATE DOMAIN -----------------------
                # ---- GET THE DOMAIN
                target_domain = Domain.objects.get(name=transition_domain_name)
                # DEBUG:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"""{TerminalColors.YELLOW}
                    > Found existing entry in Domain table for: {transition_domain_name}, {target_domain.state}
                    {TerminalColors.ENDC}""",  # noqa
                )

                # ---- UPDATE THE DOMAIN
                # update the status
                self.update_domain_status(transition_domain, target_domain, debug_on)
                # TODO: not all domains need to be updated
                # (the information is the same).
                # Need to bubble this up to the final report.

                # update dates (creation and expiration)
                if transition_domain_creation_date is not None:
                    # TODO: added this because I ran into a situation where
                    # the created_at date was null (violated a key constraint).
                    # How do we want to handle this case?
                    target_domain.created_at = transition_domain_creation_date

                if transition_domain_expiration_date is not None:
                    target_domain.expiration_date = transition_domain_expiration_date
                target_domain.save()

                return (target_domain, False)

            except Domain.MultipleObjectsReturned:
                # This exception was thrown once before during testing.
                # While the circumstances that led to corrupt data in
                # the domain table was a freak accident, and the possibility of it
                # happening again is safe-guarded by a key constraint,
                # better to keep an eye out for it since it would require
                # immediate attention.
                logger.warning(f"""
                    {TerminalColors.FAIL}
                    !!! ERROR: duplicate entries already exist in the
                    Domain table for the following domain:
                    {transition_domain_name}

                    RECOMMENDATION:
                    This means the Domain table is corrupt.  Please
                    check the Domain table data as there should be a key
                    constraint which prevents duplicate entries.

                    ----------TERMINATING----------""")
                sys.exit()
            except TransitionNotAllowed as err:
                logger.warning(f"""{TerminalColors.FAIL}
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
                    ----------SKIPPING----------""")
                return (None, False)
        else:
            # ----------------------- CREATE DOMAIN -----------------------
            # no matching entry, make one
            target_domain = Domain(
                name=str(transition_domain_name),
                state=transition_domain_status,
                expiration_date=transition_domain_expiration_date,
            )
            return (target_domain, True)

    def update_domain_status(self, transition_domain: TransitionDomain, target_domain: Domain, debug_on: bool) -> bool:
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

    # ======================================================
    # ================ DOMAIN INVITATION  ==================
    # ======================================================
    def try_add_domain_invitation(self, domain_email: str, associated_domain: Domain) -> DomainInvitation | None:
        """If no domain invitation exists for the given domain and
        e-mail, create and return a new domain invitation object.
        If one already exists, or if the email is invalid, return NONE"""

        # this should never happen, but adding it just in case
        if associated_domain is None:
            logger.warning(f"""
                        {TerminalColors.FAIL}
                        !!! ERROR: Domain cannot be null for a
                        Domain Invitation object!

                        RECOMMENDATION:
                        Somehow, an empty domain object is
                        being passed to the subroutine in charge
                        of making domain invitations. Walk through
                        the code to see what is amiss.

                        ----------TERMINATING----------""")
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
                new_domain_invitation = DomainInvitation(email=domain_email.lower(), domain=associated_domain)
                return new_domain_invitation
        return None

    # ======================================================
    # ================ DOMAIN INFORMATION  =================
    # ======================================================
    def update_domain_information(self, current: DomainInformation, target: DomainInformation, debug_on: bool) -> bool:
        # DEBUG:
        TerminalHelper.print_conditional(
            debug_on,
            (f"{TerminalColors.OKCYAN}" f"Updating: {current}" f"{TerminalColors.ENDC}"),  # noqa
        )

        updated = False

        fields_to_update = [
            "generic_org_type",
            "federal_type",
            "federal_agency",
            "organization_name",
        ]
        defaults = {field: getattr(target, field) for field in fields_to_update}
        if current != target:
            current = target
            DomainInformation.objects.filter(domain=current.domain).update(**defaults)
            updated = True

        return updated

    def update_contact_info(self, first_name, middle_name, last_name, email, phone):
        contact = None
        contacts = Contact.objects.filter(email=email)
        contact_count = contacts.count()
        # Create a new one
        if contact_count == 0:
            contact = Contact(
                first_name=first_name, middle_name=middle_name, last_name=last_name, email=email, phone=phone
            )
            contact.save()
        elif contact_count == 1:
            contact = contacts.get()
            contact.first_name = first_name
            contact.middle_name = middle_name
            contact.last_name = last_name
            contact.email = email
            contact.phone = phone
            contact.save()
        else:
            logger.warning(f"Duplicate contact found {contact}. Updating all relevant entries.")
            for c in contacts:
                c.first_name = first_name
                c.middle_name = middle_name
                c.last_name = last_name
                c.email = email
                c.phone = phone
                c.save()
            contact = contacts.first()
        return contact

    def create_new_domain_info(
        self,
        transition_domain: TransitionDomain,
        domain: Domain,
        agency_choices,
        fed_choices,
        org_choices,
        debug_on,
    ) -> DomainInformation:
        org_type = ("", "")
        fed_type = transition_domain.federal_type
        fed_agency = transition_domain.federal_agency

        # = SO Information = #
        first_name = transition_domain.first_name
        middle_name = transition_domain.middle_name
        last_name = transition_domain.last_name
        email = transition_domain.email
        phone = transition_domain.phone

        contact = self.update_contact_info(first_name, middle_name, last_name, email, phone)

        if debug_on:
            logger.info(f"Contact created: {contact}")

        org_type_current = transition_domain.generic_org_type
        match org_type_current:
            case "Federal":
                org_type = ("federal", "Federal")
            case "Interstate":
                org_type = ("interstate", "Interstate")
            case "State":
                org_type = ("state_or_territory", "State or territory")
            case "Tribal":
                org_type = ("tribal", "Tribal")
            case "County":
                org_type = ("county", "County")
            case "City":
                org_type = ("city", "City")
            case "Independent Intrastate":
                org_type = ("special_district", "Special district")

        valid_org_type = org_type in org_choices
        valid_fed_type = fed_type in fed_choices
        valid_fed_agency = fed_agency in agency_choices

        default_requester = User.get_default_user()

        new_domain_info_data = {
            "domain": domain,
            "organization_name": transition_domain.organization_name,
            "requester": default_requester,
            "senior_official": contact,
        }

        if valid_org_type:
            new_domain_info_data["generic_org_type"] = org_type[0]
        elif debug_on:
            logger.debug(f"No org type found on {domain.name}")

        if valid_fed_type and isinstance(fed_type, str):
            new_domain_info_data["federal_type"] = fed_type.lower()
        elif debug_on:
            logger.debug(f"No federal type found on {domain.name}")

        if valid_fed_agency:
            new_domain_info_data["federal_agency"] = fed_agency
        elif debug_on:
            logger.debug(f"No federal agency found on {domain.name}")

        new_domain_info = DomainInformation(**new_domain_info_data)

        # DEBUG:
        TerminalHelper.print_conditional(
            True,
            (
                f"{TerminalColors.MAGENTA}"
                f"Created Domain Information template for: {new_domain_info}"
                f"{TerminalColors.ENDC}"
            ),  # noqa
        )
        return new_domain_info

    def update_or_create_domain_information(
        self,
        transition_domain: TransitionDomain,
        agency_choices,
        fed_choices,
        org_choices,
        debug_on: bool,
    ):
        transition_domain_name = transition_domain.domain_name

        # Get associated domain
        domain_data = Domain.objects.filter(name=transition_domain.domain_name)
        if not domain_data.exists():
            logger.warn(
                f"{TerminalColors.FAIL}"
                f"WARNING: No Domain exists for:"
                f"{transition_domain_name}"
                f"{TerminalColors.ENDC}\n"
            )
            return (None, None, False)
        domain = domain_data.get()
        template_domain_information = self.create_new_domain_info(
            transition_domain,
            domain,
            agency_choices,
            fed_choices,
            org_choices,
            debug_on,
        )
        target_domain_information = None
        domain_information_exists = DomainInformation.objects.filter(domain__name=transition_domain_name).exists()
        if domain_information_exists:
            try:
                # get the existing domain information object
                target_domain_information = DomainInformation.objects.get(domain__name=transition_domain_name)
                # DEBUG:
                TerminalHelper.print_conditional(
                    debug_on,
                    (
                        f"{TerminalColors.FAIL}"
                        f"Found existing entry in Domain Information table for:"
                        f"{transition_domain_name}"
                        f"{TerminalColors.ENDC}"
                    ),  # noqa
                )

                # for existing entry, update the status to
                # the transition domain status
                self.update_domain_information(target_domain_information, template_domain_information, debug_on)
                # TODO: not all domains need to be updated
                # (the information is the same).
                # Need to bubble this up to the final report.

                return (target_domain_information, domain, False)
            except DomainInformation.MultipleObjectsReturned:
                # This should never happen (just like with the Domain Table).
                # However, because such an error did occur in the past,
                # we will watch for it in this script
                logger.warning(f"""
                    {TerminalColors.FAIL}
                    !!! ERROR: duplicate entries already exist in the
                    Domain Information table for the following domain:
                    {transition_domain_name}

                    RECOMMENDATION:
                    This means the Domain Information table is corrupt.  Please
                    check the Domain Information table data as there should be a key
                    constraint which prevents duplicate entries.

                    ----------TERMINATING----------""")
                sys.exit()
        else:
            # no matching entry, make one
            target_domain_information = template_domain_information
            # DEBUG:
            TerminalHelper.print_conditional(
                debug_on,
                (
                    f"{TerminalColors.OKCYAN}"
                    f"Adding domain information for: "
                    f"{transition_domain_name}"
                    f"{TerminalColors.ENDC}"
                ),
            )
            return (target_domain_information, domain, True)

    # C901 'Command.handle' is too complex
    def process_domain_information(
        self,
        valid_agency_choices,
        valid_fed_choices,
        valid_org_choices,
        debug_on,
        skipped_domain_information_entries,
        domain_information_to_create,
        updated_domain_information,
        debug_max_entries_to_parse,
        total_rows_parsed,
    ):
        changed_transition_domains = TransitionDomain.objects.filter(processed=False)
        for transition_domain in changed_transition_domains:
            (
                target_domain_information,
                associated_domain,
                was_created,
            ) = self.update_or_create_domain_information(
                transition_domain,
                valid_agency_choices,
                valid_fed_choices,
                valid_org_choices,
                debug_on,
            )

            debug_string = ""
            if target_domain_information is None:
                # ---------------- SKIPPED ----------------
                skipped_domain_information_entries.append(target_domain_information)
                debug_string = f"skipped domain information: {target_domain_information}"
            elif was_created:
                # DEBUG:
                TerminalHelper.print_conditional(
                    debug_on,
                    (
                        f"{TerminalColors.OKCYAN}"
                        f"Checking duplicates for: {target_domain_information}"
                        f"{TerminalColors.ENDC}"
                    ),  # noqa
                )
                # ---------------- DUPLICATE ----------------
                # The unique key constraint does not allow multiple domain
                # information objects to share the same domain
                existing_domain_information_in_to_create = next(
                    (x for x in domain_information_to_create if x.domain.name == target_domain_information.domain.name),
                    None,
                )
                # TODO: this is redundant.
                # Currently debugging....
                # running into unique key constraint error....
                existing_domain_info = DomainInformation.objects.filter(
                    domain__name=target_domain_information.domain.name
                ).exists()
                if existing_domain_information_in_to_create is not None or existing_domain_info:
                    debug_string = f"""{TerminalColors.YELLOW}
                        Duplicate Detected: {existing_domain_information_in_to_create}.
                        Cannot add duplicate Domain Information object
                        {TerminalColors.ENDC}"""
                else:
                    # ---------------- CREATED ----------------
                    domain_information_to_create.append(target_domain_information)
                    debug_string = f"created domain information: {target_domain_information}"
            elif not was_created:
                # ---------------- UPDATED ----------------
                updated_domain_information.append(target_domain_information)
                debug_string = f"updated domain information: {target_domain_information}"
            else:
                debug_string = "domain information already exists and "
                f"matches incoming data (NO CHANGES MADE): {target_domain_information}"

            # DEBUG:
            TerminalHelper.print_conditional(
                debug_on,
                (f"{TerminalColors.OKCYAN}{debug_string}{TerminalColors.ENDC}"),
            )

            # ------------------ Parse limit reached? ------------------
            # Check parse limit and exit loop if parse limit has been reached
            if self.parse_limit_reached(debug_max_entries_to_parse, total_rows_parsed):
                break
        return (
            skipped_domain_information_entries,
            domain_information_to_create,
            updated_domain_information,
        )

    # C901 'Command.handle' is too complex
    def process_domain_and_invitations(
        self,
        debug_on,
        skipped_domain_entries,
        domains_to_create,
        updated_domain_entries,
        domain_invitations_to_create,
        debug_max_entries_to_parse,
        total_rows_parsed,
    ):
        changed_transition_domains = TransitionDomain.objects.filter(processed=False)
        for transition_domain in changed_transition_domains:
            # Create some local variables to make data tracing easier
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
                f"{transition_domain_name},"
                f" {transition_domain_status},"
                f" {transition_domain_email}"
                f", {transition_domain_creation_date}, "
                f"{transition_domain_expiration_date}"
                f"{TerminalColors.ENDC}",  # noqa
            )

            # ======================================================
            # ====================== DOMAIN  =======================
            target_domain, was_created = self.update_or_create_domain(transition_domain, debug_on)

            debug_string = ""
            if target_domain is None:
                # ---------------- SKIPPED ----------------
                skipped_domain_entries.append(transition_domain_name)
                debug_string = f"skipped domain: {target_domain}"
            elif was_created:
                # ---------------- DUPLICATE ----------------
                # The unique key constraint does not allow duplicate domain entries
                # even if there are different users.
                existing_domain_in_to_create = next(
                    (x for x in domains_to_create if x.name == transition_domain_name),
                    None,
                )
                if existing_domain_in_to_create is not None:
                    debug_string = f"""{TerminalColors.YELLOW}
                        Duplicate Detected: {transition_domain_name}.
                        Cannot add duplicate entry for another username.
                        Violates Unique Key constraint.
                        {TerminalColors.ENDC}"""
                else:
                    # ---------------- CREATED ----------------
                    domains_to_create.append(target_domain)
                    debug_string = f"created domain: {target_domain}"
            elif not was_created:
                # ---------------- UPDATED ----------------
                updated_domain_entries.append(transition_domain.domain_name)
                debug_string = f"updated domain: {target_domain}"

            # DEBUG:
            TerminalHelper.print_conditional(
                debug_on,
                (f"{TerminalColors.OKCYAN} {debug_string} {TerminalColors.ENDC}"),
            )

            # ======================================================
            # ================ DOMAIN INVITATIONS ==================
            new_domain_invitation = self.try_add_domain_invitation(transition_domain_email, target_domain)
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

            # ------------------ Parse limit reached? ------------------
            # Check parse limit and exit loop if parse limit has been reached
            if self.parse_limit_reached(debug_max_entries_to_parse, total_rows_parsed):
                break
        return (
            skipped_domain_entries,
            domains_to_create,
            updated_domain_entries,
            domain_invitations_to_create,
        )

    # ======================================================
    # ===================== HANDLE  ========================
    # ======================================================
    def handle(
        self,
        **options,
    ):
        """Parse entries in TransitionDomain table
        and create (or update) corresponding entries in the
        Domain and DomainInvitation tables."""

        # grab command line arguments and store locally...
        debug_on = options.get("debug")
        debug_max_entries_to_parse = int(options.get("limitParse"))  # set to 0 to parse all entries

        self.print_debug_mode_statements(debug_on, debug_max_entries_to_parse)

        # domains to ADD
        domains_to_create = []
        domain_information_to_create = []

        # domains we UPDATED
        updated_domain_entries = []
        updated_domain_information = []

        # domains we SKIPPED
        skipped_domain_entries = []
        skipped_domain_information_entries = []

        # domain invitations to ADD
        domain_invitations_to_create = []

        # if we are limiting our parse (for testing purposes, keep
        # track of total rows parsed)
        total_rows_parsed = 0

        logger.info(f"""{TerminalColors.OKCYAN}
            ==========================
            Beginning Data Transfer
            ==========================
            {TerminalColors.ENDC}""")

        logger.info(f"""{TerminalColors.OKCYAN}
            ========= Adding Domains and Domain Invitations =========
            {TerminalColors.ENDC}""")
        (
            skipped_domain_entries,
            domains_to_create,
            updated_domain_entries,
            domain_invitations_to_create,
        ) = self.process_domain_and_invitations(
            debug_on,
            skipped_domain_entries,
            domains_to_create,
            updated_domain_entries,
            domain_invitations_to_create,
            debug_max_entries_to_parse,
            total_rows_parsed,
        )

        # First, save all Domain objects to the database
        Domain.objects.bulk_create(domains_to_create)

        # DomainInvitation.objects.bulk_create(domain_invitations_to_create)

        # TODO: this is to resolve an error where bulk_create
        # doesn't save to database in a way that invitation objects can
        # utilize.
        # Then, create DomainInvitation objects
        for invitation in domain_invitations_to_create:
            if debug_on:
                logger.info(f"Pairing invite to its domain...{invitation}")
            existing_domain = Domain.objects.filter(name=invitation.domain.name)
            # Make sure the related Domain object is saved
            if existing_domain.exists():
                invitation.domain = existing_domain.get()
            else:
                # Raise an err for now
                raise Exception(f"Domain {existing_domain} wants to be added" "but doesn't exist in the DB")
            invitation.save()

        valid_org_choices = [(name, value) for name, value in DomainRequest.OrganizationChoices.choices]
        valid_fed_choices = [value for name, value in BranchChoices.choices]
        valid_agency_choices = FederalAgency.objects.all()
        # ======================================================
        # ================= DOMAIN INFORMATION =================
        logger.info(f"""{TerminalColors.OKCYAN}
            ========= Adding Domains Information Objects =========
            {TerminalColors.ENDC}""")

        (
            skipped_domain_information_entries,
            domain_information_to_create,
            updated_domain_information,
        ) = self.process_domain_information(
            valid_agency_choices,
            valid_fed_choices,
            valid_org_choices,
            debug_on,
            skipped_domain_information_entries,
            domain_information_to_create,
            updated_domain_information,
            debug_max_entries_to_parse,
            total_rows_parsed,
        )

        TerminalHelper.print_conditional(
            debug_on,
            (f"{TerminalColors.YELLOW}" f"Trying to add: {domain_information_to_create}" f"{TerminalColors.ENDC}"),
        )
        DomainInformation.objects.bulk_create(domain_information_to_create)

        # Loop through the list of everything created, and mark it as processed
        for domain in domains_to_create:
            name = domain.name
            TransitionDomain.objects.filter(domain_name=name).update(processed=True)

        # Loop through the list of everything updated, and mark it as processed
        for name in updated_domain_entries:
            TransitionDomain.objects.filter(domain_name=name).update(processed=True)

        self.print_summary_of_findings(
            domains_to_create,
            updated_domain_entries,
            domain_invitations_to_create,
            skipped_domain_entries,
            domain_information_to_create,
            updated_domain_information,
            debug_on,
        )
