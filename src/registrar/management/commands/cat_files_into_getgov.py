"""Loads files from /tmp into our sandboxes"""
import glob
import logging

import os
import string

from django.core.management import BaseCommand

from registrar.management.commands.utility.terminal_helper import TerminalHelper


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the cat command on files from /tmp into the getgov directory."

    def add_arguments(self, parser):
        """Add our two filename arguments."""
        parser.add_argument(
            "--file_extension",
            default="txt",
            help="What file extensions to look for, like txt or gz",
        )
        parser.add_argument(
            "--directory", default="migrationdata", help="Desired directory"
        )

    def handle(self, **options):
        file_extension: str = options.get("file_extension").lstrip(".")
        directory = options.get("directory")
        helper = TerminalHelper()

        # file_extension is always coerced as str, Truthy is OK to use here.
        if not file_extension or not isinstance(file_extension, str):
            raise ValueError(f"Invalid file extension '{file_extension}'")

        matching_extensions = glob.glob(f"../tmp/*.{file_extension}")
        if not matching_extensions:
            logger.error(f"No files with the extension {file_extension} found")

        for src_file_path in matching_extensions:
            filename = os.path.basename(src_file_path)
            exit_status = -1
            do_command = True

            desired_file_path = f"{directory}/{filename}"
            if os.path.exists(desired_file_path):
                # For linter
                prompt = "Do you want to replace it?"
                replace = f"{desired_file_path} already exists. {prompt}"
                if not helper.query_yes_no(replace):
                    do_command = False

            try:
                if do_command:
                    copy_from = f"../tmp/{filename}"
                    exit_status = self.cat(copy_from, desired_file_path)
            except ValueError as err:
                raise err
            finally:
                if exit_status == 0:
                    logger.info(f"Successfully copied {filename}")
                else:
                    logger.error(f"Failed to copy {filename}")

    def cat(self, copy_from, copy_to):
        """Runs the cat command to
        copy_from a location to copy_to a location"""

        # copy_from will be system defined
        self.check_file_path(copy_from, check_directory=False)
        self.check_file_path(copy_to)

        # This command can only be ran from inside cf ssh getgov-{sandbox}
        # It has no utility when running locally, and to exploit this
        # you would have to have ssh access anyway, which is a bigger problem.
        exit_status = os.system(f"cat {copy_from} > {copy_to}")  # nosec
        return exit_status

    def check_file_path(self, file_path: str, check_directory=True):
        """Does a check on user input to ensure validity"""
        if not isinstance(file_path, str):
            raise ValueError("Invalid path provided")

        # Remove any initial/final whitespace
        file_path = file_path.strip()

        # Check for any attempts to move up in the directory structure
        if ".." in file_path and check_directory:
            raise ValueError("Moving up in the directory structure is not allowed")

        # Check for any invalid characters
        valid_chars = f"/-_.() {string.ascii_letters}{string.digits}"
        for char in file_path:
            if char not in valid_chars:
                raise ValueError(f"Invalid character {char} in file path")

        return file_path
