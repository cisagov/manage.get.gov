import logging
import re
import sys
import os
from django.core.management import BaseCommand

logger = logging.getLogger(__name__)

# Dynamically set the default folder path to 'src/registrar/models' relative to the script's location
DEFAULT_FOLDER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../models')
DEFAULT_FOLDER_PATH = os.path.normpath(DEFAULT_FOLDER_PATH)

# Set the default file path to a specific file within the DEFAULT_FOLDER_PATH
DEFAULT_FILE_PATH = "" #os.path.join(DEFAULT_FOLDER_PATH, 'domain.py')

# Boolean to control whether to group by function
group_by_function = False

# Boolean to control whether to only print a summary of unique EPP commands
summary_only = True


class Command(BaseCommand):
    help = "Parse Python files in a folder or specific file for EPP commands and print them to the console."

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_path",
            type=str,
            nargs="?",
            default=DEFAULT_FOLDER_PATH,
            help="Path to the folder containing Python files to scan for EPP commands",
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
