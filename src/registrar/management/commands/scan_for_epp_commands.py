import logging
import re
import sys
import os
from django.core.management import BaseCommand

logger = logging.getLogger(__name__)
#-----------------------------------------------------------------------
#                           SUMMARY
# This script was created with the help of AI to quickly scaffold a way
# to analyze our codebase for EPP commands.  It was used as part of an
# effort to document out EPP command event flow, and can be reused
# in the event that we update this flow.
#
# You can choose to scan all the files in a given folder, or just a specific
# file.  This can be done by setting the DEFAULT_FOLDER_PATH and DEFAULT_FILE_PATH
# respectively, or by passing in parameters to the script execution command in the console.
#
# There are 3 outputs to choose from:
# - Summary only (a simple list of all EPP commads found. Set summary_only=True to select this output)
# - Group by command (After each EPP commands a list of all the parent functions that call them is also printed to the console. Set summary_only=False and group_by_function=False)
# - Group by function (The list of EPP commands are grouped by all the parent functions that call them. Set summary_only=False and group_by_function=True)
#-----------------------------------------------------------------------

#---------------------------
#         DEFAULTS
# Used if no parameters were given
#---------------------------
# Default folder to scan for EPP commands
DEFAULT_FOLDER_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../models'))

# Dfault file to scan for EPP commands (if this is null, will scan default folder path)
DEFAULT_FILE_PATH = os.path.join(DEFAULT_FOLDER_PATH, 'domain.py')

#---------------------------
#     OUTPUT SETTINGS
#---------------------------
# Boolean to control whether to group by function.
#
# If TRUE, the output will be a list of all functions
# that have EPP commands, along with the EPP commands
# The format of the output will be
# FUNCTION_NAME
#   |-- EPP_COMMAND_NAME
#   |-- EPP_COMMAND_NAME
#   |-- (etc)
#
# If FALSE, the output will be a list of all EPP commands
# along wih all the parent functions that call them
# The format of the output in this case will be
# EPP_COMMAND_NAME
#   |-- FUNCTION_NAME
#   |-- FUNCTION_NAME
#   |-- (etc)
group_by_function = False

# Boolean to control whether to only print a summary of unique EPP commands
# If set to true, the above lists will not print and instead we will just 
# get a distinct list of all EPP commands found
summary_only = True


#---------------------------
#     MAIN FUNCTION
#---------------------------
class Command(BaseCommand):
    help = "Parse Python files in a folder or specific file for EPP commands and print them to the console."

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_path",
            type=str,
            nargs="?",
            default=DEFAULT_FOLDER_PATH,
            help="Path to the folder containing Python files to scan for EPP commands (optional)",
        )
        parser.add_argument(
            "file_path",
            type=str,
            nargs="?",
            default=DEFAULT_FILE_PATH,
            help="Path to a specific Python file to scan for EPP commands (optional)",
        )

    def handle(self, *args, **options):
        folder_path = options["folder_path"]
        file_path = options["file_path"]
        
        if file_path:  # If file_path is provided, scan that file
            logger.info(f"Scanning file: {file_path}")
            self.process_file(file_path)
        else:  # Otherwise, scan the entire folder
            logger.info(f"Scanning folder: {folder_path}")

            if not os.path.isdir(folder_path):
                logger.error("Invalid folder path. Please provide a valid directory.")
                return

            for file_name in os.listdir(folder_path):
                if file_name.endswith(".py"):
                    file_path = os.path.join(folder_path, file_name)
                    self.process_file(file_path)

    def process_file(self, file_path):
        logger.info(f"Scanning file: {file_path}")
        try:
            self.print_to_console(file_path)
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}. Please check the path and try again.")

    def extract_epp_commands(self, content):
        pattern = r"commands\.([a-zA-Z_]+)"
        matches = re.findall(pattern, content)
        return list(set(matches))  # Remove duplicates

    def analyze_functions_and_commands(self, content):
        # Find all functions in the file
        function_pattern = r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s?\(.*\):"
        function_matches = re.finditer(function_pattern, content)

        function_to_commands = {}
        command_to_functions = {}

        # Traverse the file and gather function -> command and command -> function mappings
        last_pos = 0
        for match in function_matches:
            function_name = match.group(1)
            function_start = match.start()
            function_end = content.find('def ', function_start + 1)  # Find the start of the next function

            # If there's no next function, go until the end of the file
            function_body = content[function_start:function_end if function_end != -1 else None]

            commands_in_function = re.findall(r"commands\.([a-zA-Z_]+)", function_body)

            if commands_in_function:
                function_to_commands[function_name] = list(set(commands_in_function))  # Store unique commands
                for command in function_to_commands[function_name]:
                    if command not in command_to_functions:
                        command_to_functions[command] = []
                    command_to_functions[command].append(function_name)

        return function_to_commands, command_to_functions

    def print_to_console(self, file_path):
        with open(file_path, "r") as file:
            content = file.read()

            if summary_only:
                # Only print a summary of unique EPP commands
                print("Summary of unique EPP commands:")
                epp_commands = self.extract_epp_commands(content)
                if epp_commands:
                    for command in epp_commands:
                        print(f"   |--{command}")
                    logger.info(f"EPP commands from {file_path} printed to console.")
                else:
                    logger.info(f"No EPP commands found in {file_path}.")
                    
            else:
                function_to_commands, command_to_functions = self.analyze_functions_and_commands(content)
                if group_by_function:
                    # Group commands by function
                    for function, commands in function_to_commands.items():
                        print(f"{function}")
                        for command in commands:
                            print(f"   |--{command}")
                else:
                    # Output commands and their parent functions
                    for command, functions in command_to_functions.items():
                        print(f"{command}")
                        for function in functions:
                            print(f"   |--{function}")
