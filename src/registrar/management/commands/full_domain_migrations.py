"""Data migration:
 1 - generates a report of data integrity across all
 transition domain related tables
 2 - allows users to run all migration scripts for
 transition domain data
"""

import logging
import argparse
import sys
import os

from django.test import Client

from django_fsm import TransitionNotAllowed  # type: ignore

from django.core.management import BaseCommand

from registrar.models import (
    Domain,
    DomainInformation,
    DomainInvitation,
    TransitionDomain,
    User,
)

from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper
)

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = """ """

    def add_arguments(self, parser):
        """
        OPTIONAL ARGUMENTS:
        --runLoaders
        A boolean (default to true), which triggers running
        all scripts (in sequence) for transition domain migrations

        --triggerLogins
        A boolean (default to true), which triggers running
        simulations of user logins for each user in domain invitation

        --loaderDirectory
        The location of the files used for load_transition_domain migration script
        EXAMPLE USAGE:
        > --loaderDirectory /app/tmp

        --loaderFilenames
        The files used for load_transition_domain migration script.  
        Must appear IN ORDER and separated by spaces: 
        EXAMPLE USAGE:
        > --loaderFilenames domain_contacts_filename.txt contacts_filename.txt domain_statuses_filename.txt
        where...
        - domain_contacts_filename is the Data file with domain contact information
        - contacts_filename is the Data file with contact information
        - domain_statuses_filename is the Data file with domain status information

        --sep
        Delimiter for the loaders to correctly parse the given text files.
        (usually this can remain at default value of |)

        --debug
        A boolean (default to true), which activates additional print statements

        --limitParse
        Used by the loaders (load_transition_domain) to set the limit for the
        number of data entries to insert.  Set to 0 (or just don't use this
        argument) to parse every entry. This was provided primarily for testing
        purposes

        --resetTable
        Used by the loaders to trigger a prompt for deleting all table entries.  
        Useful for testing purposes, but USE WITH CAUTION
        """

        parser.add_argument("--runLoaders",
            help="Runs all scripts (in sequence) for transition domain migrations",
            action=argparse.BooleanOptionalAction)
        
        parser.add_argument("--triggerLogins",
            help="Simulates a user login for each user in domain invitation",
            action=argparse.BooleanOptionalAction)

        # The following file arguments have default values for running in the sandbox
        parser.add_argument(
            "--loaderDirectory",
            default="migrationData",
            help="The location of the files used for load_transition_domain migration script"
        )
        parser.add_argument(
            "--loaderFilenames",
            default="escrow_domain_contacts.daily.gov.GOV.txt escrow_contacts.daily.gov.GOV.txt escrow_domain_statuses.daily.gov.GOV.txt",
            help="""The files used for load_transition_domain migration script.  
            Must appear IN ORDER and separated by spaces: 
            domain_contacts_filename.txt contacts_filename.txt domain_statuses_filename.txt
            
            where...
            - domain_contacts_filename is the Data file with domain contact information
            - contacts_filename is the Data file with contact information
            - domain_statuses_filename is the Data file with domain status information"""
        )

        parser.add_argument("--sep", default="|", help="Delimiter character for the loader files")

        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

        parser.add_argument(
            "--limitParse", default=0, help="Sets max number of entries to load"
        )

        parser.add_argument(
            "--resetTable",
            help="Deletes all data in the TransitionDomain table",
            action=argparse.BooleanOptionalAction,
        )

    

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

        #TODO: would filteredRelation be faster?

        missing_domains = []
        duplicate_domains = []
        missing_domain_informations = []
        missing_domain_invites = []
        for transition_domain in TransitionDomain.objects.all():# DEBUG:
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
            matching_domain_invitations = DomainInvitation.objects.filter(email=transition_domain_email.lower(), 
                                                                          domain__name=transition_domain_name)

            if len(matching_domains) == 0:
                TerminalHelper.print_conditional(debug_on, f"""{TerminalColors.YELLOW}Missing Domain{TerminalColors.ENDC}""")
                missing_domains.append(transition_domain_name)
            elif len(matching_domains) > 1:
                TerminalHelper.print_conditional(debug_on, f"""{TerminalColors.YELLOW}Duplicate Domain{TerminalColors.ENDC}""")
                duplicate_domains.append(transition_domain_name)
            if len(matching_domain_informations) == 0:
                TerminalHelper.print_conditional(debug_on, f"""{TerminalColors.YELLOW}Missing Domain Information{TerminalColors.ENDC}""")
                missing_domain_informations.append(transition_domain_name)
            if len(matching_domain_invitations) == 0:
                TerminalHelper.print_conditional(debug_on, f"""{TerminalColors.YELLOW}Missing Domain Invitation{TerminalColors.ENDC}""")
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
            {TerminalColors.YELLOW}{missing_domains_as_string}{TerminalColors.OKGREEN}

            {total_duplicate_domains} Duplicate Domains:
            (These are transition domains which have duplicate entries in the Domain Table)
            {TerminalColors.YELLOW}{duplicate_domains_as_string}{TerminalColors.OKGREEN}

            {total_missing_domain_informations} Domain Information Entries missing:
            (These are transition domains which have no entries in the Domain Information Table)
            {TerminalColors.YELLOW}{missing_domain_informations_as_string}{TerminalColors.OKGREEN}

            {total_missing_domain_invitations} Domain Invitations missing:
            (These are transition domains which have no entires in the Domain Invitation Table)
            {TerminalColors.YELLOW}{missing_domain_invites_as_string}{TerminalColors.OKGREEN}
            {TerminalColors.ENDC}
            """
        )
    
    def prompt_for_execution(self, command_string: str, prompt_title: str) -> bool:
        """Prompts the user to inspect the given terminal command string
        and asks if they wish to execute it.  If the user responds (y),
        execute the command"""

        # Allow the user to inspect the command string
        # and ask if they wish to proceed
        proceed_execution = TerminalHelper.query_yes_no(
            f"""{TerminalColors.OKCYAN}
            =====================================================
            {prompt_title}
            =====================================================
            *** IMPORTANT:  VERIFY THE FOLLOWING COMMAND LOOKS CORRECT ***

            {command_string}
            {TerminalColors.FAIL}
            Proceed? (Y = proceed, N = skip)
            {TerminalColors.ENDC}"""
        )

        # If the user decided to proceed executing the command,
        # run the command for loading transition domains.
        # Otherwise, exit this subroutine.
        if not proceed_execution:
            sys.exit()
        
        self.execute_command(command_string)

        return True
    
    def execute_command(self, command_string:str):
        """Executes the given command string"""

        logger.info(f"""{TerminalColors.OKCYAN}
        ==== EXECUTING... ====
        {TerminalColors.ENDC}""")
        os.system(f"{command_string}")
    
    def run_load_transition_domain_script(self,
                                          file_location: str,
                                          domain_contacts_filename: str,
                                          contacts_filename: str,
                                          domain_statuses_filename: str,
                                          sep: str,
                                          reset_table: bool,
                                          debug_on: bool,
                                          prompts_enabled: bool,
                                          debug_max_entries_to_parse: int):
        """Runs the load_transition_domain script"""
        # Create the command string
        command_string = "./manage.py load_transition_domain "
        command_string += file_location+domain_contacts_filename + " "
        command_string += file_location+contacts_filename + " "
        command_string += file_location+domain_statuses_filename + " "
        if sep is not None and sep != "|":
            command_string += f"--sep {sep} "
        if reset_table:
            command_string += "--resetTable "
        if debug_on:
            command_string += "--debug "
        if debug_max_entries_to_parse > 0:
            command_string += f"--limitParse {debug_max_entries_to_parse} "

        # Execute the command string
        if prompts_enabled:
            self.prompt_for_execution(command_string, "Running load_transition_domain script")
            return
        self.execute_command(command_string)
        
    
    def run_transfer_script(self, debug_on:bool, prompts_enabled: bool):
        """Runs the transfer_transition_domains_to_domains script"""
        # Create the command string
        command_string = "./manage.py transfer_transition_domains_to_domains "
        if debug_on:
            command_string += "--debug "
        # Execute the command string
        if prompts_enabled:
            self.prompt_for_execution(command_string, "Running transfer_transition_domains_to_domains script")
            return
        self.execute_command(command_string)


    def run_send_invites_script(self, debug_on: bool, prompts_enabled: bool):
        """Runs the send_domain_invitations script"""
        # Create the command string...
        command_string = "./manage.py send_domain_invitations -s"
        # Execute the command string
        if prompts_enabled:
            self.prompt_for_execution(command_string, "Running send_domain_invitations script")
            return
        self.execute_command(command_string)


    def run_migration_scripts(self,
                            prompts_enabled: bool,
                            options):
        """Runs the following migration scripts (in order): 
                1 - imports for trans domains
                2 - transfer to domain & domain invitation"""
        
        # Get arguments
        sep = options.get("sep")
        reset_table = options.get("resetTable")
        debug_on = options.get("debug")
        debug_max_entries_to_parse = int(
            options.get("limitParse")
        )

        # Grab filepath information from the arguments
        file_location = options.get("loaderDirectory")+"/"
        filenames = options.get("loaderFilenames").split()
        if len(filenames) < 3:
            filenames_as_string = "{}".format(", ".join(map(str, filenames)))
            logger.info(f"""
            {TerminalColors.FAIL}
            --loaderFilenames expected 3 filenames to follow it,
            but only {len(filenames)} were given:
            {filenames_as_string}

            PLEASE MODIFY THE SCRIPT AND TRY RUNNING IT AGAIN
            ============= TERMINATING =============
            {TerminalColors.ENDC}
            """)
            sys.exit()
        domain_contacts_filename = filenames[0]
        contacts_filename = filenames[1]
        domain_statuses_filename = filenames[2]

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

                ....for the following files:
                - domain contacts: {domain_contacts_filename}
                - contacts: {contacts_filename}
                - domain statuses: {domain_statuses_filename}

                {TerminalColors.FAIL}
                Does this look correct?{TerminalColors.ENDC}"""
            )

            # If the user rejected the filepath information
            # as incorrect, prompt the user to provide 
            # correct file inputs in their original command
            # prompt and exit this subroutine
            if not files_are_correct:
                logger.info(f"""
                {TerminalColors.YELLOW}
                PLEASE Re-Run the script with the correct file location and filenames: 
                
                EXAMPLE:
                docker compose run -T app ./manage.py test_domain_migration --runLoaders --loaderDirectory /app/tmp --loaderFilenames escrow_domain_contacts.daily.gov.GOV.txt escrow_contacts.daily.gov.GOV.txt escrow_domain_statuses.daily.gov.GOV.txt
                
                """)
                return
        
        # Proceed executing the migration scripts
        self.run_load_transition_domain_script(file_location,
                                          domain_contacts_filename,
                                          contacts_filename,
                                          domain_statuses_filename,
                                          sep,
                                          reset_table,
                                          debug_on,
                                          prompts_enabled,
                                          debug_max_entries_to_parse)
        self.run_transfer_script(debug_on, prompts_enabled)


    def simulate_user_logins(self, debug_on):
        """Simulates logins for users (this will add
        Domain Information objects to our tables)"""

        logger.info(f""
                    f"{TerminalColors.OKCYAN}"
                    f"================== SIMULATING LOGINS =================="
                    f"{TerminalColors.ENDC}")
        
        # for invite in DomainInvitation.objects.all(): #TODO: limit to our stuff
        #     #DEBUG:
        #     TerminalHelper.print_conditional(debug_on,
        #                                      f"{TerminalColors.OKCYAN}"
        #                                      f"Processing invite: {invite}"
        #                                      f"{TerminalColors.ENDC}")
        #     # get a user with this email address
        #     user, user_created = User.objects.get_or_create(email=invite.email, username=invite.email)
        #     #DEBUG:
        #     TerminalHelper.print_conditional(user_created,
        #                                      f"""{TerminalColors.OKCYAN}No user found (creating temporary user object){TerminalColors.ENDC}""")
        #     TerminalHelper.print_conditional(debug_on,
        #                                      f"""{TerminalColors.OKCYAN}Executing first-time login for user: {user}{TerminalColors.ENDC}""")
        #     user.first_login()
        #     if user_created:
        #         logger.info(f"""{TerminalColors.YELLOW}(Deleting temporary user object){TerminalColors.ENDC}""")
        #         user.delete()


    def handle(
        self,
        **options,
    ):
        """
        Does the following;
        1 - run loader scripts
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
        debug_on = options.get("debug")
        prompts_enabled = debug_on #TODO: add as argument?
        run_loaders_enabled = options.get("runLoaders")
        simulate_user_login_enabled = options.get("triggerLogins")
        TerminalHelper.print_conditional(
                debug_on,
                f"""{TerminalColors.OKCYAN}
                ----------DEBUG MODE ON----------
                Detailed print statements activated.
                {TerminalColors.ENDC}
                """
            )
        TerminalHelper.print_conditional(
                run_loaders_enabled,
                f"""{TerminalColors.OKCYAN}
                ----------RUNNING LOADERS ON----------
                All migration scripts will be run before
                analyzing the data.
                {TerminalColors.ENDC}
                """
            )
        TerminalHelper.print_conditional(
                run_loaders_enabled,
                f"""{TerminalColors.OKCYAN}
                ----------TRIGGER LOGINS ON----------
                Will be simulating user logins
                {TerminalColors.ENDC}
                """
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

        # STEP 1 -- RUN LOADERS
        # Run migration scripts if specified by user
        if run_loaders_enabled:
            self.run_migration_scripts(options, prompts_enabled)
            prompt_continuation_of_analysis = True
        
        # STEP 2 -- SIMULATE LOGINS
        # Simulate user login for each user in domain
        # invitation if specified by user OR if running
        # migration scripts.
        # (NOTE: Although users can choose to run login
        # simulations separately (for testing purposes),
        # if we are running all migration scripts, we should
        # automatically execute this as the final step
        # to ensure Domain Information objects get added
        # to the database.)
        if run_loaders_enabled:
            if prompts_enabled:
                simulate_user_login_enabled = TerminalHelper.query_yes_no(
                f"""{TerminalColors.FAIL}
                Proceed with simulating user logins?
                {TerminalColors.ENDC}"""
                )
                if not simulate_user_login_enabled:
                    return
            self.simulate_user_logins(debug_on)
            prompt_continuation_of_analysis = True
       
        # STEP 3 -- SEND INVITES
        if prompts_enabled:
            proceed_with_sending_invites = TerminalHelper.query_yes_no(
                f"""{TerminalColors.FAIL}
                Proceed with sending user invites?
                {TerminalColors.ENDC}"""
                )
            if not proceed_with_sending_invites:
                return
        self.run_send_invites_script(debug_on)
        prompt_continuation_of_analysis = True

        # STEP 4 -- ANALYZE TABLES & GENERATE REPORT
        # Analyze tables for corrupt data...
        if prompt_continuation_of_analysis & prompts_enabled:
            # ^ (only prompt if we ran steps 1 and/or 2)
            analyze_tables = TerminalHelper.query_yes_no(
                f"""{TerminalColors.FAIL}
                Proceed with table analysis?
                {TerminalColors.ENDC}"""
            )
            if not analyze_tables:
                return
        self.compare_tables(debug_on)
