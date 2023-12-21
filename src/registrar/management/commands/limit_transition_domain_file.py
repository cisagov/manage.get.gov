import csv
import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import TerminalColors

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = """Removes entries from the second file based on the entries in the first file."""

    def add_arguments(self, parser):
        parser.add_argument(
            "--whitelist_filename",
            help="A file that contains a list of domains to be whitelisted",
        )
        parser.add_argument(
            "--source_filename",
            help="The source file from which all domains not in the whitelist will be removed",
        )
        parser.add_argument(
            "--output_filename",
            help="The output file where the result will be stored",
        )
        parser.add_argument("--sep", default="|", help="Delimiter character")

    def handle(self, *args, **options):
        whitelist_filename = options['whitelist_filename']
        source_filename = options['source_filename']
        output_filename = options['output_filename']
        sep = options['sep']

        whitelist = self.get_whitelist(whitelist_filename)
        self.remove_entries(source_filename, whitelist, output_filename, sep)

    def get_whitelist(self, whitelist_filename):
        whitelist = set()
        with open(whitelist_filename, 'r') as file:
            for line in file:
                whitelist.add(line.strip().upper())
        return whitelist

    def remove_entries(self, source_filename, whitelist, output_filename, sep):
        with open(source_filename, 'r') as source_file, open(output_filename, 'w') as output_file:
            reader = csv.reader(source_file, delimiter=sep)
            writer = csv.writer(output_file, delimiter=sep)
            whitelisted_domains = []
            failed_to_whitelist = []

            logger.info(f"Preparing to whitelist {len(whitelist)} domains")
            for row in reader:
                try:
                    domain_name = row[0].upper()
                    if domain_name in whitelist:
                        writer.writerow(row)
                        whitelisted_domains.append(domain_name)
                except Exception as err:
                    logger.error(f"Failed to whitelist {domain_name}")
                    logger.error(err)
                    failed_to_whitelist.append(domain_name)
            logger.info(
                f"{TerminalColors.OKGREEN}"
                f"Whitelisted {len(whitelisted_domains)} domains: {whitelisted_domains}"
                f"{TerminalColors.ENDC}"
            )
            logger.error(
                f"{TerminalColors.FAIL}"
                f"Failed to whitelist {len(failed_to_whitelist)} domains: {failed_to_whitelist}}"
                f"{TerminalColors.ENDC}"
            )
            logger.info(
                f"{TerminalColors.OKBLUE}"
                f"File {output_filename} was created"
                f"{TerminalColors.ENDC}"
            )
