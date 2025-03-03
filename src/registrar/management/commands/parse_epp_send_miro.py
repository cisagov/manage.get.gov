import logging
import re
import sys
import os
from django.core.management import BaseCommand
from epplibwrapper import commands
import miro

logger = logging.getLogger(__name__)

DEFAULT_FOLDER_PATH = "/path/to/default/folder"
DEFAULT_BOARD_ID = "default_board_id"


class Command(BaseCommand):
    help = "Parse Python files in a folder for EPP commands and send them to an existing Miro board."

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_path",
            type=str,
            nargs="?",
            default=DEFAULT_FOLDER_PATH,
            help="Path to the folder containing Python files to scan for EPP commands",
        )
        parser.add_argument(
            "board_id", type=str, nargs="?", default=DEFAULT_BOARD_ID, help="Miro board ID to send the sticky notes to"
        )

    def handle(self, *args, **options):
        folder_path = options["folder_path"]
        board_id = options["board_id"]
        logger.info(f"Scanning folder: {folder_path} for Miro board: {board_id}")

        if not os.path.isdir(folder_path):
            logger.error("Invalid folder path. Please provide a valid directory.")
            return

        miro_board = miro.Board(board_id)

        for file_name in os.listdir(folder_path):
            if file_name.endswith(".py"):
                file_path = os.path.join(folder_path, file_name)
                self.process_file(file_path, miro_board)

    def process_file(self, file_path, miro_board):
        logger.info(f"Scanning file: {file_path}")

        try:
            with open(file_path, "r") as file:
                content = file.read()
                epp_commands = self.extract_epp_commands(content)

                if epp_commands:
                    self.send_to_miro(file_path, epp_commands, miro_board)
                    logger.info(f"EPP commands from {file_path} sent to Miro.")
                else:
                    logger.info(f"No EPP commands found in {file_path}.")
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}. Please check the path and try again.")

    def extract_epp_commands(self, content):
        pattern = r"commands\.([a-zA-Z_]+)"
        matches = re.findall(pattern, content)
        return list(set(matches))  # Remove duplicates

    def send_to_miro(self, file_path, epp_commands, miro_board):
        file_name = os.path.basename(file_path)
        sticky_text = f"{file_name}\n\nEPP Commands:\n" + "\n".join(epp_commands)
        miro_board.create_sticky_note(sticky_text)
        logger.info(f"Sticky note created in Miro for {file_name}.")
