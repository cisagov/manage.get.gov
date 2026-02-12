"""Loads files from /tmp into our sandboxes"""

import glob
import logging

import os
import shutil

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
        parser.add_argument("--directory", default="migrationdata", help="Desired directory")

    def handle(self, **options):
        file_extension: str = options.get("file_extension").lstrip(".")
        directory = options.get("directory")
        helper = TerminalHelper()

        # file_extension is always coerced as str, Truthy is OK to use here.
        if not file_extension or not isinstance(file_extension, str):
            raise ValueError(f"Invalid file extension '{file_extension}'")

        matching_files = glob.glob(f"../tmp/*.{file_extension}")
        if not matching_files:
            logger.error(f"No files with the extension {file_extension} found")
            return None

        for src_file_path in matching_files:
            filename = os.path.basename(src_file_path)

            desired_file_path = os.path.join(directory, filename)
            if os.path.exists(desired_file_path):
                # For linter
                prompt = "Do you want to replace it?"
                replace = f"{desired_file_path} already exists. {prompt}"
                if not helper.query_yes_no(replace):
                    continue

            src_file_path = f"../tmp/{filename}"
            shutil.copy(src_file_path, desired_file_path)
