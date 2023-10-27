import logging
import os
import sys

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


class TerminalHelper:
    def query_yes_no(question: str, default="yes") -> bool:
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

    def print_conditional(print_condition: bool, print_statement: str):
        """This function reduces complexity of debug statements
        in other functions.
        It uses the logger to write the given print_statement to the
        terminal if print_condition is TRUE"""
        # DEBUG:
        if print_condition:
            logger.info(print_statement)
    

    def prompt_for_execution(system_exit_on_terminate: bool, 
                             info_to_inspect: str, 
                             prompt_title: str) -> bool:
        """Create to reduce code complexity.
        Prompts the user to inspect the given string
        and asks if they wish to execute it.  
        Returns true if the user responds (y),
        Returns false if the user responds (n)"""

        action_description_for_selecting_no = "skip"
        if system_exit_on_terminate:
            action_description_for_selecting_no = "exit"

        # Allow the user to inspect the command string
        # and ask if they wish to proceed
        proceed_execution = TerminalHelper.query_yes_no(
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