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
    def bulk_update_fields(model_class, update_list, fields_to_update, batch_size=1000, quiet=False):
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
            ScriptDataHelper.bulk_update_fields(Domain, page.object_list, ["first_ready"])

        Returns: A queryset of the updated objets
        """
        if not quiet:
            logger.info(f"{TerminalColors.YELLOW} Bulk updating fields... {TerminalColors.ENDC}")
        # Create a Paginator object. Bulk_update on the full dataset
        # is too memory intensive for our current app config, so we can chunk this data instead.
        paginator = Paginator(update_list, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            model_class.objects.bulk_update(page.object_list, fields_to_update)

    @staticmethod
    def bulk_create_fields(model_class, update_list, batch_size=1000, return_created=False, quiet=False):
        """
        This function performs a bulk create operation on a specified Django model class in batches.
        It uses Django's Paginator to handle large datasets in a memory-efficient manner.

        Parameters:
        model_class: The Django model class that you want to perform the bulk update on.
                    This should be the actual class, not a string of the class name.

        update_list: A list of model instances that you want to update. Each instance in the list
                    should already have the updated values set on the instance.

        batch_size:  The maximum number of model instances to update in a single database query.
                    Defaults to 1000. If you're dealing with models that have a large number of fields,
                    or large field values, you may need to decrease this value to prevent out-of-memory errors.
        Usage:
            ScriptDataHelper.bulk_add_fields(Domain, page.object_list)

        Returns: A queryset of the added objects
        """
        if not quiet:
            logger.info(f"{TerminalColors.YELLOW} Bulk adding fields... {TerminalColors.ENDC}")

        created_objs = []
        paginator = Paginator(update_list, batch_size)
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            all_created = model_class.objects.bulk_create(page.object_list)
            if return_created:
                created_objs.extend([created.id for created in all_created])
        if return_created:
            return model_class.objects.filter(id__in=created_objs)
        return None


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

    def mass_update_records(
        self, object_class, filter_conditions, fields_to_update, debug=True, verbose=False, show_record_count=False
    ):
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

            show_record_count: Whether to show a 'Record 1/10' dialog when running update.
                Default: False.

        Raises:
            NotImplementedError: If you do not define update_record before using this function.
            TypeError: If custom_filter is not Callable.
        """

        records = object_class.objects.filter(**filter_conditions) if filter_conditions else object_class.objects.all()

        # apply custom filter
        records = self.custom_filter(records)
        records_length = len(records)

        readable_class_name = self.get_class_name(object_class)

        # for use in the execution prompt.
        proposed_changes = (
            "==Proposed Changes==\n"
            f"Number of {readable_class_name} objects to change: {records_length}\n"
            f"These fields will be updated on each record: {fields_to_update}"
        )

        if verbose:
            proposed_changes = f"{proposed_changes}\n" f"These records will be updated: {list(records.all())}"

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
        for i, record in enumerate(records, start=1):
            if show_record_count:
                logger.info(f"{TerminalColors.BOLD}Record {i}/{records_length}{TerminalColors.ENDC}")
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
        self.bulk_update_fields(object_class, to_update, fields_to_update)

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

    def bulk_update_fields(self, object_class, to_update, fields_to_update):
        """Bulk updates the given fields"""
        ScriptDataHelper.bulk_update_fields(object_class, to_update, fields_to_update)

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
        create,
        update,
        skip,
        fail,
        debug: bool,
        log_header="============= FINISHED =============",
        skipped_header="----- SOME DATA WAS INVALID (NEEDS MANUAL PATCHING) -----",
        failed_header="----- UPDATE FAILED -----",
        display_as_str=False,
        detailed_prompt_title="Do you wish to see the full list of failed, skipped and updated records?",
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

        Output Format (if count > 0 for each category):
            [log_header]
            Created W entries
            Updated X entries
            [skipped_header]
            Skipped updating Y entries
            [failed_header]
            Failed to update Z entries

        Debug output (if enabled):
        - Directly prints each list for each category (add, update, etc)
        - Converts each item to string if display_as_str is True
        """
        counts = {
            "created": len(create),
            "updated": len(update),
            "skipped": len(skip),
            "failed": len(fail),
        }

        # Give the user the option to see failed / skipped records if any exist.
        display_detailed_logs = False
        if not debug and counts["failed"] > 0 or counts["skipped"] > 0:
            display_detailed_logs = TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=False,
                prompt_message=f'You will see {counts["failed"]} failed and {counts["skipped"]} skipped records.',
                verify_message="** Some records were skipped, or some failed to update. **",
                prompt_title=detailed_prompt_title,
            )

        non_zero_counts = {category: count for category, count in counts.items() if count > 0}
        messages = []
        for category, count in non_zero_counts.items():
            match category:
                case "created":
                    label, values, debug_color = "Created", create, TerminalColors.OKBLUE
                case "updated":
                    label, values, debug_color = "Updated", update, TerminalColors.OKCYAN
                case "skipped":
                    label, values, debug_color = "Skipped updating", skip, TerminalColors.YELLOW
                    messages.append(skipped_header)
                case "failed":
                    label, values, debug_color = "Failed to update", fail, TerminalColors.FAIL
                    messages.append(failed_header)
            messages.append(f"{label} {count} entries")

            # Print debug messages (prints the internal add, update, skip, fail lists)
            if debug or display_detailed_logs:
                display_values = [str(v) for v in values] if display_as_str else values
                debug_message = f"{label}: {display_values}"
                logger.info(f"{debug_color}{debug_message}{TerminalColors.ENDC}")

        final_message = f"\n{log_header}\n" + "\n".join(messages)
        if counts["failed"] > 0:
            logger.error(f"{TerminalColors.FAIL}{final_message}{TerminalColors.ENDC}")
        elif counts["skipped"] > 0:
            logger.warning(f"{TerminalColors.YELLOW}{final_message}{TerminalColors.ENDC}")
        else:
            logger.info(f"{TerminalColors.OKGREEN}{final_message}{TerminalColors.ENDC}")

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
        return log_method(colored_message, exc_info=exc_info)
