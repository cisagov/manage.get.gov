# Tests database connection behavior by running create_federal_portfolio script in dry-run mode

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
import time
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test database connection behavior using portfolio creation script"

    def add_arguments(self, parser):
        parser.add_argument("--iterations", type=int, default=5, help="Number of test iterations")
        parser.add_argument("--delay", type=int, default=0, help="Delay between tests in seconds")
        parser.add_argument(
            "--agencies",
            nargs="+",
            default=["Department of Defense", "Department of State", "Department of Treasury", "Department of Justice"],
            help="Agency names to cycle through",
        )

    def handle(self, *args, **options):
        iterations = options["iterations"]
        delay = options["delay"]
        agencies = options["agencies"]

        self.stdout.write(f"Testing database connections ({iterations} iterations)...")

        conn_info = self._get_connection_info()
        self.stdout.write(f"Initial state: {conn_info}")
        logger.info(f"DB_CONNECTION_TEST_START: {conn_info}")

        durations = []
        start_time = time.time()

        for i in range(iterations):
            agency = agencies[i % len(agencies)]
            iteration_start = time.time()
            queries_before = len(connection.queries)

            logger.info(f"DB_CONN_START: iteration={i}, queries={queries_before}")

            self._run_portfolio_script(agency, i)

            duration = time.time() - iteration_start
            durations.append(duration)
            queries_after = len(connection.queries)
            new_queries = queries_after - queries_before

            log_msg = (
                f"Test {i+1}: duration={duration:.3f}s, "
                f"queries={new_queries}, agency='{agency}', "
                f"total_queries={queries_after}"
            )

            logger.info(f"DB_CONN_END: iteration={i}, new_queries={new_queries}, total_queries={queries_after}")
            logger.info(f"DB_CONNECTION_TEST: {log_msg}")
            self.stdout.write(f"  {log_msg}")

            if delay > 0 and i < iterations - 1:
                time.sleep(delay)

        total_duration = time.time() - start_time
        self._print_summary(durations, total_duration, iterations)

    def _run_portfolio_script(self, agency_name, iteration):
        try:
            call_command(
                "create_federal_portfolio",
                agency_name=agency_name,
                parse_requests=True,
                parse_domains=True,
                dry_run=True,
                verbosity=0,
            )
            return True
        except Exception as e:
            logger.warning(f"Iteration {iteration} failed with {agency_name}: {e}")
            return False

    def _print_summary(self, durations, total_duration, iterations):
        if not durations:
            self.stdout.write("No successful operations to analyze")
            return

        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)

        # Check for connection reuse pattern
        if len(durations) > 1:
            first_duration = durations[0]
            later_avg = sum(durations[1:]) / len(durations[1:])
            reuse_likely = later_avg < first_duration * 0.8
        else:
            reuse_likely = False

        summary = (
            f"CONNECTION TEST SUMMARY:\n"
            f"  Total duration: {total_duration:.3f}s\n"
            f"  Avg duration: {avg_duration:.3f}s\n"
            f"  Min/Max: {min_duration:.3f}s / {max_duration:.3f}s\n"
            f"  Connection reuse likely: {'Yes' if reuse_likely else 'No'}"
        )

        self.stdout.write(f"\n{summary}")
        logger.info(f"DB_CONNECTION_TEST_COMPLETE: {summary.replace(chr(10), ' | ')}")

    def _get_connection_info(self):
        return f"queries={len(connection.queries)}, " f"vendor={connection.vendor}"
