"""Loads files from /tmp into our sandboxes"""
import glob
import csv
import logging

import os

from django.core.management import BaseCommand


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

        # file_extension is always coerced as str, Truthy is OK to use here.
        if not file_extension or not isinstance(file_extension, str):
            raise ValueError(f"Invalid file extension '{file_extension}'")

        matching_extensions = glob.glob(f"../tmp/*.{file_extension}")
        if not matching_extensions:
            logger.error(f"No files with the extension {file_extension} found")

        for src_file_path in matching_extensions:
            filename = os.path.basename(src_file_path)
            do_command = True
            exit_status: int

            desired_file_path = f"{directory}/{filename}"
            if os.path.exists(desired_file_path):
                replace = input(
                    f"{desired_file_path} already exists. Do you want to replace it? (y/n) "
                )
                if replace.lower() != "y":
                    do_command = False

            if do_command:
                copy_from = f"../tmp/{filename}"
                self.cat(copy_from, desired_file_path)
                exit_status = os.system(f"cat ../tmp/{filename} > {desired_file_path}")

            if exit_status == 0:
                logger.info(f"Successfully copied {filename}")
            else:
                logger.info(f"Failed to copy {filename}")

    def cat(self, copy_from, copy_to):
        exit_status = os.system(f"cat {copy_from} > {copy_to}")
        return exit_status
