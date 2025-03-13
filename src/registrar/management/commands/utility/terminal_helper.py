import logging
import sys
from abc import ABC, abstractmethod
from django.core.paginator import Paginator
from django.db.models import Model
from django.db.models.manager import BaseManager
from typing import List
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
    Contains an ABC for generic populate scripts.

    This template provides reusable logging and bulk updating functions for
    mass-updating fields.
    """

    # Optional script-global config variables. For the most part, you can leave these untouched.
    # Defines what prompt_for_execution displays as its header when you first start the script
    prompt_title: str = "Do you wish to proceed?"

    # The header when printing the script run summary (after the script finishes)
    run_summary_header = None

    @abstractmethod
    def update_record(self, record):
        """Defines how we update each field.

        raises:
            NotImplementedError: If not defined before calling mass_update_records.
        """
        raise NotImplementedError

    def mass_update_records(self, object_class, filter_conditions, fields_to_update, debug=True, verbose=False):
        """Loops through each valid "object_class" object - specified by filter_conditions - and
        updates fields defined by fields_to_update using update_record.

        Parameters:
            object_class: The Django model class that you want to perform the bulk update on.
                This should be the actual class, not a string of the class name.

            filter_conditions: dictionary of valid Django Queryset filter conditions
                (e.g. {'verification_type__isnull'=True}).

            fields_to_update: List of strings specifying which fields to update.
                (e.g. ["first_ready_date", "last_submitted_date"])

            debug: Whether to log script run summary in debug mode.
                Default: True.

            verbose: Whether to print a detailed run summary *before* run confirmation.
                Default: False.

        Raises:
            NotImplementedError: If you do not define update_record before using this function.
            TypeError: If custom_filter is not Callable.
        """

        records = object_class.objects.filter(**filter_conditions) if filter_conditions else object_class.objects.all()

        # apply custom filter
        records = self.custom_filter(records)

        readable_class_name = self.get_class_name(object_class)

        # for use in the execution prompt.
        proposed_changes = f"""==Proposed Changes==
            Number of {readable_class_name} objects to change: {len(records)}
            These fields will be updated on each record: {fields_to_update}
            """

        if verbose:
            proposed_changes = f"""{proposed_changes}
            These records will be updated: {list(records.all())}
            """

        # Code execution will stop here if the user prompts "N"
        TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=proposed_changes,
            prompt_title=self.prompt_title,
        )
        logger.info("Updating...")

        to_update: List[object_class] = []
        to_skip: List[object_class] = []
        failed_to_update: List[object_class] = []
        for record in records:
            try:
                if not self.should_skip_record(record):
                    self.update_record(record)
                    to_update.append(record)
                else:
                    to_skip.append(record)
            except Exception as err:
                fail_message = self.get_failure_message(record)
                failed_to_update.append(record)
                logger.error(err)
                logger.error(fail_message)

        # Do a bulk update on the desired field
        ScriptDataHelper.bulk_update_fields(object_class, to_update, fields_to_update)

        # Log what happened
        TerminalHelper.log_script_run_summary(
            to_update,
            failed_to_update,
            to_skip,
            [],
            debug=debug,
            log_header=self.run_summary_header,
            display_as_str=True,
        )

    def get_class_name(self, sender) -> str:
        """Returns the class name that we want to display for the terminal prompt.
        Example: DomainRequest => "Domain Request"
        """
        return sender._meta.verbose_name if getattr(sender, "_meta") else sender

    def get_failure_message(self, record) -> str:
        """Returns the message that we will display if a record fails to update"""
        return f"{TerminalColors.FAIL}" f"Failed to update {record}" f"{TerminalColors.ENDC}"

    def should_skip_record(self, record) -> bool:  # noqa
        """Defines the condition in which we should skip updating a record. Override as needed.
        The difference between this and custom_filter is that records matching these conditions
        *will* be included in the run but will be skipped (and logged as such)."""
        # By default - don't skip
        return False

    def custom_filter(self, records: BaseManager[Model]) -> BaseManager[Model]:
        """Override to define filters that can't be represented by django queryset field lookups.
        Applied to individual records *after* filter_conditions. True means"""
        return records


class TerminalHelper:

    @staticmethod
    def log_script_run_summary(
        to_update,
        failed_to_update,
        skipped,
        to_add,
        debug: bool,
        log_header=None,
        skipped_header=None,
        failed_header=None,
        display_as_str=False,
    ):
        """Generates a formatted summary of script execution results with colored output.
        
        Displays counts and details of successful, failed, and skipped operations.
        In debug mode or when prompted, shows full record details.
        Uses color coding: green for success, yellow for skipped, red for failures.

        Args:
            to_update: Records that were successfully updated
            failed_to_update: Records that failed to update
            skipped: Records that were intentionally skipped
            to_add: Records that were newly added
            debug: If True, shows detailed record information
            log_header: Custom header for the summary (default: "FINISHED")
            skipped_header: Custom header for skipped records section
            failed_header: Custom header for failed records section
            display_as_str: If True, converts records to strings for display

        Output Format:
            [Header]
            Added: X entries
            Updated: Y entries 
            Skipped: Z entries
            Failed: W entries

            Debug output (if enabled):
            - Full record details for each category
            - Color coded by operation type
        """
        add_count = len(to_add)
        update_count = len(to_update)
        skipped_count = len(skipped)
        failed_count = len(failed_to_update)
        # Label, count, values, and debug-specific log color
        count_msgs = {
            "added": ("Added", add_count, to_add, TerminalColors.OKBLUE),
            "updated": ("Updated", update_count, to_update, TerminalColors.OKCYAN),
            "skipped": ("Skipped updating", skipped_count, skipped, TerminalColors.YELLOW),
            "failed": ("Failed to update", failed_count, failed_to_update, TerminalColors.FAIL),
        }

        if log_header is None:
            log_header = "============= FINISHED ==============="

        if skipped_header is None:
            skipped_header = "----- SOME DATA WAS INVALID (NEEDS MANUAL PATCHING) -----"

        if failed_header is None:
            failed_header = "----- UPDATE FAILED -----"

        # Give the user the option to see failed / skipped records if any exist.
        display_detailed_logs = False
        if not debug and failed_count > 0 or skipped_count > 0:
            display_detailed_logs = TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=False,
                prompt_message=f"You will see {failed_count} failed and {skipped_count} skipped records.",
                verify_message="** Some records were skipped, or some failed to update. **",
                prompt_title="Do you wish to see the full list of failed, skipped and updated records?",
            )

        change_occurred = False
        messages = [f"\n{log_header}"]
        for change_type, dict_tuple in count_msgs.items():
            label, count, values, debug_log_color = dict_tuple
            if count > 0:
                # Print debug messages (prints the internal add, update, skip, fail lists)
                if debug or display_detailed_logs:
                    display_values = [str(v) for v in values] if display_as_str else values
                    message = f"{label}: {display_values}"
                    TerminalHelper.colorful_logger(logger.info, debug_log_color, message)

                # Get the sub-header for fail conditions
                if change_type == "failed":
                    messages.append(failed_header)
                if change_type == "skipped":
                    messages.append(skipped_header)

                # Print the change count
                messages.append(f"{label} {count} entries")
                change_occurred = True

        if not change_occurred:
            messages.append("No changes occurred.")

        if failed_count > 0:
            TerminalHelper.colorful_logger("ERROR", "FAIL", "\n".join(messages))
        elif skipped_count > 0:
            TerminalHelper.colorful_logger("WARNING", "YELLOW", "\n".join(messages))
        else:
            TerminalHelper.colorful_logger("INFO", "OKGREEN", "\n".join(messages))

    @staticmethod
    def query_yes_no(question: str, default="yes"):
        """Ask a yes/no question via raw_input() and return their answer.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
                It must be "yes" (the default), "no" or None (meaning
                an answer is required of the user).

        The "answer" return value is True for "yes" or False for "no".

        Raises:
            ValueError: When "default" is not "yes", "no", or None.
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
        Allows for answer "e" to exit.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
                It must be "yes" (the default), "no" or None (meaning
                an answer is required of the user).

        The "answer" return value is True for "yes" or False for "no".

        Raises:
            ValueError: When "default" is not "yes", "no", or None.
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
    def prompt_for_execution(
        system_exit_on_terminate: bool, prompt_message: str, prompt_title: str, verify_message=None
    ) -> bool:
        """Create to reduce code complexity.
        Prompts the user to inspect the given string
        and asks if they wish to proceed.
        If the user responds (y), returns TRUE
        If the user responds (n), either returns FALSE
        or exits the system if system_exit_on_terminate = TRUE"""

        action_description_for_selecting_no = "skip, E = exit"
        if system_exit_on_terminate:
            action_description_for_selecting_no = "exit"

        if verify_message is None:
            verify_message = "*** IMPORTANT:  VERIFY THE FOLLOWING LOOKS CORRECT ***"

        # Allow the user to inspect the command string
        # and ask if they wish to proceed
        proceed_execution = TerminalHelper.query_yes_no_exit(
            f"\n{TerminalColors.OKCYAN}"
            "=====================================================\n"
            f"{prompt_title}\n"
            "=====================================================\n"
            f"{verify_message}\n"
            f"{prompt_message}\n"
            f"{TerminalColors.FAIL}"
            f"Proceed? (Y = proceed, N = {action_description_for_selecting_no})"
            f"{TerminalColors.ENDC}"
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

    @staticmethod
    def colorful_logger(log_level, color, message, exc_info=True):
        """Adds some color to your log output.

        Args:
            log_level: str | Logger.method -> Desired log level. ex: logger.info or "INFO"
            color: str | TerminalColors -> Output color. ex: TerminalColors.YELLOW or "YELLOW"
            message: str -> Message to display.
            exc_info: bool -> Whether the log should print exc_info or not
        """

        if isinstance(log_level, str) and hasattr(logger, log_level.lower()):
            log_method = getattr(logger, log_level.lower())
        else:
            log_method = log_level

        if isinstance(color, str) and hasattr(TerminalColors, color.upper()):
            terminal_color = getattr(TerminalColors, color.upper())
        else:
            terminal_color = color

        colored_message = f"{terminal_color}{message}{TerminalColors.ENDC}"
        log_method(colored_message, exc_info=exc_info)
