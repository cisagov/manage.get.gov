"""Data migration:
1 - generates a report of data integrity across all
transition domain related tables
2 - allows users to run all migration scripts for
transition domain data
"""

import logging
import argparse

from django.core.management import BaseCommand
from django.core.management import call_command

from registrar.models import (
    Domain,
    DomainInformation,
    DomainInvitation,
    TransitionDomain,
)

from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """ """  # TODO: update this!

    def add_arguments(self, parser):
        """
        OPTIONAL ARGUMENTS:
        --runMigrations
        A boolean (default to true), which triggers running
        all scripts (in sequence) for transition domain migrations

        --migrationDirectory
        The location of the files used for load_transition_domain migration script
        EXAMPLE USAGE:
        > --migrationDirectory /app/tmp

        --migrationJSON
        The name of the JSON file used for load_transition_domain migration script
        EXAMPLE USAGE:
        > --migrationJSON migrationFilepaths.json

        --sep
        Delimiter for the migration scripts to correctly parse the given text files.
        (usually this can remain at default value of |)

        --debug
        Activates additional print statements

        --disablePrompts
        Disables terminal prompts that allows the user to step through each portion of this
        script.

        --limitParse
        Used by the migration scripts (load_transition_domain) to set the limit for the
        number of data entries to insert.  Set to 0 (or just don't use this
        argument) to parse every entry. This was provided primarily for testing
        purposes

        --resetTable
        Used by the migration scripts to trigger a prompt for deleting all table entries.
        Useful for testing purposes, but USE WITH CAUTION
        """  # noqa - line length, impacts readability

        parser.add_argument(
            "--runMigrations",
            help="Runs all scripts (in sequence) for transition domain migrations",
            action=argparse.BooleanOptionalAction,
        )

        # --triggerLogins
        # A boolean (default to true), which triggers running
        # simulations of user logins for each user in domain invitation
        parser.add_argument(
            "--triggerLogins",
            help="Simulates a user login for each user in domain invitation",
            action=argparse.BooleanOptionalAction,
        )

        # The following file arguments have default values for running in the sandbox

        # TODO: make this a mandatory argument
        # (if/when we strip out defaults, it will be mandatory)
        # TODO: use the migration directory arg or force user to type FULL filepath?
        parser.add_argument(
            "--migrationJSON",
            default="migrationFilepaths.json",
            help=("A JSON file that holds the location and filenames" "of all the data files used for migrations"),
        )

        # TODO: deprecate this once JSON module is done? (or keep as an override)
        parser.add_argument(
            "--migrationDirectory",
            default="migrationdata",
            help=("The location of the files used for load_transition_domain migration script"),
        )

        parser.add_argument("--sep", default="|", help="Delimiter character for the migration files")

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument("--disablePrompts", action=argparse.BooleanOptionalAction)

        parser.add_argument("--limitParse", default=0, help="Sets max number of entries to load")

        parser.add_argument(
            "--resetTable",
            help="Deletes all data in the TransitionDomain table",
            action=argparse.BooleanOptionalAction,
        )

    # ======================================================
    # ===============    DATA ANALYSIS    ==================
    # ======================================================

    def compare_tables(self, debug_on: bool):
        """Does a diff between the transition_domain and the following tables:
        domain, domain_information and the domain_invitation.

        Produces the following report (printed to the terminal):
            #1 - Print any domains that exist in the transition_domain table
            but not in their corresponding domain, domain information or
            domain invitation tables.
            #2 - Print which table this domain is missing from
            #3- Check for duplicate entries in domain or
            domain_information tables and print which are
            duplicates and in which tables
        """

        logger.info(
            f"""{TerminalColors.OKCYAN}
            ============= BEGINNING ANALYSIS ===============
            {TerminalColors.ENDC}
            """
        )

        # TODO: would filteredRelation be faster?

        missing_domains = []
        duplicate_domains = []
        missing_domain_informations = []
        missing_domain_invites = []
        for transition_domain in TransitionDomain.objects.all():  # DEBUG:
            transition_domain_name = transition_domain.domain_name
            transition_domain_email = transition_domain.username

            TerminalHelper.print_conditional(
                debug_on,
                f"{TerminalColors.OKCYAN}Checking: {transition_domain_name} {TerminalColors.ENDC}",  # noqa
            )

            # Check Domain table
            matching_domains = Domain.objects.filter(name=transition_domain_name)
            # Check Domain Information table
            matching_domain_informations = DomainInformation.objects.filter(domain__name=transition_domain_name)
            # Check Domain Invitation table
            matching_domain_invitations = DomainInvitation.objects.filter(
                email=transition_domain_email.lower(),
                domain__name=transition_domain_name,
            )

            if len(matching_domains) == 0:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"""{TerminalColors.YELLOW}Missing Domain{TerminalColors.ENDC}""",
                )
                missing_domains.append(transition_domain_name)
            elif len(matching_domains) > 1:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"""{TerminalColors.YELLOW}Duplicate Domain{TerminalColors.ENDC}""",
                )
                duplicate_domains.append(transition_domain_name)
            if len(matching_domain_informations) == 0:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"""{TerminalColors.YELLOW}Missing Domain Information
                    {TerminalColors.ENDC}""",
                )
                missing_domain_informations.append(transition_domain_name)
            if len(matching_domain_invitations) == 0:
                TerminalHelper.print_conditional(
                    debug_on,
                    f"""{TerminalColors.YELLOW}Missing Domain Invitation
                    {TerminalColors.ENDC}""",
                )
                missing_domain_invites.append(transition_domain_name)

        total_missing_domains = len(missing_domains)
        total_duplicate_domains = len(duplicate_domains)
        total_missing_domain_informations = len(missing_domain_informations)
        total_missing_domain_invitations = len(missing_domain_invites)

        missing_domains_as_string = "{}".format(", ".join(map(str, missing_domains)))
        duplicate_domains_as_string = "{}".format(", ".join(map(str, duplicate_domains)))
        missing_domain_informations_as_string = "{}".format(", ".join(map(str, missing_domain_informations)))
        missing_domain_invites_as_string = "{}".format(", ".join(map(str, missing_domain_invites)))

        logger.info(
            f"""{TerminalColors.OKGREEN}
            ============= FINISHED ANALYSIS ===============

            {total_missing_domains} Missing Domains:
            (These are transition domains that are missing from the Domain Table)
            {TerminalColors.YELLOW}{missing_domains_as_string}
            {TerminalColors.OKGREEN}
            {total_duplicate_domains} Duplicate Domains:
            (These are transition domains which have duplicate
            entries in the Domain Table)
            {TerminalColors.YELLOW}{duplicate_domains_as_string}
            {TerminalColors.OKGREEN}
            {total_missing_domain_informations} Domain Information Entries missing:
            (These are transition domains which have no entries
            in the Domain Information Table)
            {TerminalColors.YELLOW}{missing_domain_informations_as_string}
            {TerminalColors.OKGREEN}
            {total_missing_domain_invitations} Domain Invitations missing:
            (These are transition domains which have no entires in
            the Domain Invitation Table)
            {TerminalColors.YELLOW}{missing_domain_invites_as_string}
            {TerminalColors.OKGREEN}
            {TerminalColors.ENDC}
            """
        )

    # ======================================================
    # =================    MIGRATIONS    ===================
    # ======================================================
    def run_load_transition_domain_script(
        self,
        migration_json_filename: str,
        file_directory: str,
        sep: str,
        reset_table: bool,
        debug_on: bool,
        prompts_enabled: bool,
        debug_max_entries_to_parse: int,
    ):
        if file_directory and file_directory[-1] != "/":
            file_directory += "/"
        json_filepath = migration_json_filename
        """Runs the load_transition_domain script"""
        # Create the command string
        command_script = "load_transition_domain"
        command_string = f"./manage.py {command_script} " f"{json_filepath} "
        if sep is not None and sep != "|":
            command_string += f"--sep {sep} "
        if reset_table:
            command_string += "--resetTable "
        if debug_on:
            command_string += "--debug "
        if debug_max_entries_to_parse > 0:
            command_string += f"--limitParse {debug_max_entries_to_parse} "
        if file_directory:
            command_string += f"--directory {file_directory}"

        # Execute the command string
        proceed = False
        if prompts_enabled:
            proceed = TerminalHelper.prompt_for_execution(
                True,
                command_string,
                "Running load_transition_domain script",
            )

        # TODO: make this somehow run inside TerminalHelper prompt
        if proceed or not prompts_enabled:
            call_command(
                command_script,
                json_filepath,
                sep=sep,
                resetTable=reset_table,
                debug=debug_on,
                limitParse=debug_max_entries_to_parse,
                directory=file_directory,
            )

    def run_transfer_script(self, debug_on: bool, prompts_enabled: bool):
        """Runs the transfer_transition_domains_to_domains script"""
        # Create the command string
        command_script = "transfer_transition_domains_to_domains"
        command_string = f"./manage.py {command_script}"
        if debug_on:
            command_string += "--debug "
        # Execute the command string
        proceed = False
        if prompts_enabled:
            proceed = TerminalHelper.prompt_for_execution(
                True,
                command_string,
                "Running transfer_transition_domains_to_domains script",
            )
        # TODO: make this somehow run inside TerminalHelper prompt
        if proceed or not prompts_enabled:
            call_command(command_script)

    def run_send_invites_script(self, debug_on: bool, prompts_enabled: bool):
        """Runs the send_domain_invitations script"""
        # Create the command string...
        command_script = "send_domain_invitations"
        command_string = f"./manage.py {command_script} -s"
        # Execute the command string
        proceed = False
        if prompts_enabled:
            proceed = TerminalHelper.prompt_for_execution(
                False,
                command_string,
                "Running send_domain_invitations script",
            )

        # TODO: make this somehow run inside TerminalHelper prompt
        if proceed or not prompts_enabled:
            call_command(command_script, send_emails=True)

    def run_migration_scripts(
        self,
        migration_json_filename,
        file_location,
        sep,
        reset_table,
        debug_on,
        prompts_enabled,
        debug_max_entries_to_parse,
    ):
        """Runs the following migration scripts (in order):
        1 - imports for trans domains
        2 - transfer to domain & domain invitation"""

        if prompts_enabled:
            # Allow the user to inspect the filepath
            # data given in the arguments, and prompt
            # the user to verify this info before proceeding
            files_are_correct = TerminalHelper.query_yes_no(
                f"""
                {TerminalColors.OKCYAN}
                *** IMPORTANT:  VERIFY THE FOLLOWING ***

                The migration scripts are looking in directory....
                {file_location}

                ....for the following JSON:
                {migration_json_filename}

                {TerminalColors.FAIL}
                Does this look correct?{TerminalColors.ENDC}"""
            )

            # If the user rejected the filepath information
            # as incorrect, prompt the user to provide
            # correct file inputs in their original command
            # prompt and exit this subroutine
            if not files_are_correct:
                logger.info(
                    f"""
                {TerminalColors.YELLOW}
                PLEASE Re-Run the script with the correct
                JSON filename and directory:
                """
                )
                return

        # Proceed executing the migration scripts
        self.run_load_transition_domain_script(
            migration_json_filename,
            file_location,
            sep,
            reset_table,
            debug_on,
            prompts_enabled,
            debug_max_entries_to_parse,
        )
        self.run_transfer_script(debug_on, prompts_enabled)

    def handle(
        self,
        **options,
    ):
        """
        Does the following;
        1 - run migration scripts
        2 - simulate logins
        3 - send domain invitations (Emails should be sent to the appropriate users
        note that all moved domains should now be accessible
        on django admin for an analyst)
        4 - analyze the data for transition domains
        and generate a report
        """

        # SETUP
        # Grab all arguments relevant to
        # orchestrating which parts of this script
        # should execute.  Print some indicators to
        # the terminal so the user knows what is
        # enabled.

        # Get arguments
        debug_on = options.get("debug")
        prompts_enabled = not options.get("disablePrompts")
        run_migrations_enabled = options.get("runMigrations")

        TerminalHelper.print_conditional(
            debug_on,
            f"""{TerminalColors.OKCYAN}
                ----------DEBUG MODE ON----------
                Detailed print statements activated.
                {TerminalColors.ENDC}
                """,
        )
        TerminalHelper.print_conditional(
            run_migrations_enabled,
            f"""{TerminalColors.OKCYAN}
                ----------RUNNING MIGRATIONS ON----------
                All migration scripts will be run before
                analyzing the data.
                {TerminalColors.ENDC}
                """,
        )
        TerminalHelper.print_conditional(
            run_migrations_enabled,
            f"""{TerminalColors.OKCYAN}
                ----------TRIGGER LOGINS ON----------
                Will be simulating user logins
                {TerminalColors.ENDC}
                """,
        )

        # If a user decides to run all migration
        # scripts, they may or may not wish to
        # proceed with analysis of the data depending
        # on the results of the migration.
        # Provide a breakpoint for them to decide
        # whether to continue or not.
        # The same will happen if simulating user
        # logins (to allow users to run only that
        # portion of the script if desired)
        prompt_continuation_of_analysis = False

        # STEP 1 -- RUN MIGRATIONS
        # Run migration scripts if specified by user
        if run_migrations_enabled:
            # grab arguments for running migrations
            sep = options.get("sep")
            reset_table = options.get("resetTable")
            debug_max_entries_to_parse = int(options.get("limitParse"))

            # Grab filepath information from the arguments
            file_location = options.get("migrationDirectory")
            migration_json_filename = options.get("migrationJSON")

            # Run migration scripts
            self.run_migration_scripts(
                migration_json_filename,
                file_location,
                sep,
                reset_table,
                debug_on,
                prompts_enabled,
                debug_max_entries_to_parse,
            )
            prompt_continuation_of_analysis = True

        # STEP 2 -- SEND INVITES
        proceed_with_sending_invites = run_migrations_enabled
        if prompts_enabled and run_migrations_enabled:
            proceed_with_sending_invites = TerminalHelper.query_yes_no(
                f"""{TerminalColors.FAIL}
                Proceed with sending user invites for all transition domains?
                (Y = proceed, N = skip)
                {TerminalColors.ENDC}"""
            )
        if proceed_with_sending_invites:
            self.run_send_invites_script(debug_on, prompts_enabled)
            prompt_continuation_of_analysis = True

        # STEP 3 -- ANALYZE TABLES & GENERATE REPORT
        # Analyze tables for corrupt data...
        if prompt_continuation_of_analysis and prompts_enabled:
            # ^ (only prompt if we ran steps 1 and/or 2)
            analyze_tables = TerminalHelper.query_yes_no(
                f"""{TerminalColors.FAIL}
                Proceed with table analysis?
                (Y = proceed, N = exit)
                {TerminalColors.ENDC}"""
            )
            if not analyze_tables:
                return
        self.compare_tables(debug_on)
