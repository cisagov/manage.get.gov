import logging
import sys
from abc import ABC, abstractmethod
from django.core.paginator import Paginator
from typing import List
from django.core.management import BaseCommand
from registrar.utility.enums import LogCode

logger = logging.getLogger(__name__)


class TerminalColors:
    """Colors for terminal outputs
    (makes reading the logs WAY easier)"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[35m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BackgroundLightYellow = "\033[103m"


class ScriptDataHelper:
    """Helper method with utilities to speed up development of scripts that do DB operations"""

    @staticmethod
    def bulk_update_fields(model_class, update_list, fields_to_update, batch_size=1000):
        """
        This function performs a bulk update operation on a specified Django model class in batches.
        It uses Django's Paginator to handle large datasets in a memory-efficient manner.

        Parameters:
        model_class: The Django model class that you want to perform the bulk update on.
                    This should be the actual class, not a string of the class name.

        update_list: A list of model instances that you want to update. Each instance in the list
                    should already have the updated values set on the instance.

        batch_size:  The maximum number of model instances to update in a single database query.
                    Defaults to 1000. If you're dealing with models that have a large number of fields,
                    or large field values, you may need to decrease this value to prevent out-of-memory errors.

        fields_to_update: Specifies which fields to update.

        Usage:
            bulk_update_fields(Domain, page.object_list, ["first_ready"])
        """
        logger.info(f"{TerminalColors.YELLOW} Bulk updating fields... {TerminalColors.ENDC}")
        # Create a Paginator object. Bulk_update on the full dataset
        # is too memory intensive for our current app config, so we can chunk this data instead.
        paginator = Paginator(update_list, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            model_class.objects.bulk_update(page.object_list, fields_to_update)


class PopulateScriptTemplate(ABC):
    """
    Contains an ABC for generic populate scripts
    """

    def mass_populate_field(self, sender, filter_conditions, fields_to_update):
        """Loops through each valid "sender" object - specified by filter_conditions - and
        updates fields defined by fields_to_update using populate_function.

        You must define populate_field before you can use this function.
        """

        objects = sender.objects.filter(**filter_conditions)

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            info_to_inspect=f"""
            ==Proposed Changes==
            Number of {sender} objects to change: {len(objects)}
            These fields will be updated on each record: {fields_to_update}
            """,
            prompt_title="Do you wish to patch this data?",
        )
        logger.info("Updating...")

        to_update: List[sender] = []
        failed_to_update: List[sender] = []
        for updated_object in objects:
            try:
                self.populate_field(updated_object)
                to_update.append(updated_object)
            except Exception as err:
                to_update.append(updated_object)
                logger.error(err)
                logger.error(f"{TerminalColors.FAIL}" f"Failed to update {updated_object}" f"{TerminalColors.ENDC}")

        # Do a bulk update on the first_ready field
        ScriptDataHelper.bulk_update_fields(sender, to_update, fields_to_update)

        # Log what happened
        TerminalHelper.log_script_run_summary(to_update, failed_to_update, skipped=[], debug=True)

    @abstractmethod
    def populate_field(self, field_to_update):
        """Defines how we update each field. Must be defined before using mass_populate_field."""
        pass


class TerminalHelper:
    @staticmethod
    def log_script_run_summary(to_update, failed_to_update, skipped, debug: bool, log_header=None):
        """Prints success, failed, and skipped counts, as well as
        all affected objects."""
        update_success_count = len(to_update)
        update_failed_count = len(failed_to_update)
        update_skipped_count = len(skipped)

        if log_header is None:
            log_header = "============= FINISHED ==============="

        # Prepare debug messages
        debug_messages = {
            "success": (f"{TerminalColors.OKCYAN}Updated: {to_update}{TerminalColors.ENDC}\n"),
            "skipped": (f"{TerminalColors.YELLOW}Skipped: {skipped}{TerminalColors.ENDC}\n"),
            "failed": (f"{TerminalColors.FAIL}Failed: {failed_to_update}{TerminalColors.ENDC}\n"),
        }

        # Print out a list of everything that was changed, if we have any changes to log.
        # Otherwise, don't print anything.
        TerminalHelper.print_conditional(
            debug,
            f"{debug_messages.get('success') if update_success_count > 0 else ''}"
            f"{debug_messages.get('skipped') if update_skipped_count > 0 else ''}"
            f"{debug_messages.get('failed') if update_failed_count > 0 else ''}",
        )

        if update_failed_count == 0 and update_skipped_count == 0:
            logger.info(
                f"""{TerminalColors.OKGREEN}
                {log_header}
                Updated {update_success_count} entries
                {TerminalColors.ENDC}
                """
            )
        elif update_failed_count == 0:
            logger.warning(
                f"""{TerminalColors.YELLOW}
                {log_header}
                Updated {update_success_count} entries
                ----- SOME DATA WAS INVALID (NEEDS MANUAL PATCHING) -----
                Skipped updating {update_skipped_count} entries
                {TerminalColors.ENDC}
                """
            )
        else:
            logger.error(
                f"""{TerminalColors.FAIL}
                {log_header}
                Updated {update_success_count} entries
                ----- UPDATE FAILED -----
                Failed to update {update_failed_count} entries,
                Skipped updating {update_skipped_count} entries
                {TerminalColors.ENDC}
                """
            )

    @staticmethod
    def query_yes_no(question: str, default="yes"):
        """Ask a yes/no question via raw_input() and return their answer.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
                It must be "yes" (the default), "no" or None (meaning
                an answer is required of the user).

        The "answer" return value is True for "yes" or False for "no".
        """
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)

        while True:
            logger.info(question + prompt)
            choice = input().lower()
            if default is not None and choice == "":
                return valid[default]
            elif choice in valid:
                return valid[choice]
            else:
                logger.info("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")

    @staticmethod
    def query_yes_no_exit(question: str, default="yes"):
        """Ask a yes/no question via raw_input() and return their answer.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
                It must be "yes" (the default), "no" or None (meaning
                an answer is required of the user).

        The "answer" return value is True for "yes" or False for "no".
        """
        valid = {
            "yes": True,
            "y": True,
            "ye": True,
            "no": False,
            "n": False,
            "e": "exit",
        }
        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)

        while True:
            logger.info(question + prompt)
            choice = input().lower()
            if default is not None and choice == "":
                return valid[default]
            elif choice in valid:
                if valid[choice] == "exit":
                    sys.exit()
                return valid[choice]
            else:
                logger.info("Please respond with a valid selection.\n")

    @staticmethod
    def array_as_string(array_to_convert: List[str]) -> str:
        array_as_string = "{}".format("\n".join(map(str, array_to_convert)))
        return array_as_string

    @staticmethod
    def print_conditional(
        print_condition: bool,
        print_statement: str,
        log_severity: LogCode = LogCode.DEFAULT,
    ):
        """This function reduces complexity of debug statements
        in other functions.
        It uses the logger to write the given print_statement to the
        terminal if print_condition is TRUE.

        print_condition: bool -> Prints if print_condition is TRUE

        print_statement: str -> The statement to print

        log_severity: str -> Determines the severity to log at
        """
        # DEBUG:
        if print_condition:
            match log_severity:
                case LogCode.ERROR:
                    logger.error(print_statement)
                case LogCode.WARNING:
                    logger.warning(print_statement)
                case LogCode.INFO:
                    logger.info(print_statement)
                case LogCode.DEBUG:
                    logger.debug(print_statement)
                case _:
                    logger.info(print_statement)

    @staticmethod
    def prompt_for_execution(system_exit_on_terminate: bool, info_to_inspect: str, prompt_title: str) -> bool:
        """Create to reduce code complexity.
        Prompts the user to inspect the given string
        and asks if they wish to proceed.
        If the user responds (y), returns TRUE
        If the user responds (n), either returns FALSE
        or exits the system if system_exit_on_terminate = TRUE"""

        action_description_for_selecting_no = "skip, E = exit"
        if system_exit_on_terminate:
            action_description_for_selecting_no = "exit"

        # Allow the user to inspect the command string
        # and ask if they wish to proceed
        proceed_execution = TerminalHelper.query_yes_no_exit(
            f"""{TerminalColors.OKCYAN}
            =====================================================
            {prompt_title}
            =====================================================
            *** IMPORTANT:  VERIFY THE FOLLOWING LOOKS CORRECT ***

            {info_to_inspect}
            {TerminalColors.FAIL}
            Proceed? (Y = proceed, N = {action_description_for_selecting_no})
            {TerminalColors.ENDC}"""
        )

        # If the user decided to proceed return true.
        # Otherwise, either return false or exit this subroutine.
        if not proceed_execution:
            if system_exit_on_terminate:
                sys.exit()
            return False
        return True

    @staticmethod
    def get_file_line_count(filepath: str) -> int:
        with open(filepath, "r") as file:
            li = file.readlines()
        total_line = len(li)
        return total_line

    @staticmethod
    def print_to_file_conditional(print_condition: bool, filename: str, file_directory: str, file_contents: str):
        """Sometimes logger outputs get insanely huge."""
        if print_condition:
            # Add a slash if the last character isn't one
            if file_directory and file_directory[-1] != "/":
                file_directory += "/"
            # Assemble filepath
            filepath = f"{file_directory}{filename}.txt"
            # Write to file
            logger.info(f"{TerminalColors.MAGENTA}Writing to file " f" {filepath}..." f"{TerminalColors.ENDC}")
            with open(f"{filepath}", "w+") as f:
                f.write(file_contents)
