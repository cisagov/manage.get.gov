from subprocess import run, CalledProcessError  # nosec

from django.core.management.base import BaseCommand, CommandError


class LinterError(Exception):
    pass


class Command(BaseCommand):
    """
    Helper command for running installed linters.

    Run using `./manage.py lint`.
    """

    help = "Runs linters: flake8 black mypy bandit"

    # Add new linters here.
    #
    # To maintain security while using subprocess, avoid passing user input
    # and, in all cases, make sure to use a list (not a string) for flags/args
    # as this will quote the output.
    linters = {
        "flake8": {
            "purpose": "Linting",
            "args": ["flake8", ".", "--count", "--show-source", "--statistics"],
        },
        "black": {
            "purpose": "Formatting",
            "args": ["black", "--check", "."],
        },
        "mypy": {
            "purpose": "Type checking",
            "args": ["mypy", "."],
        },
        "bandit": {
            "purpose": "Security scanning",
            "args": ["bandit", "-r", "."],
        },
    }

    def add_arguments(self, parser):
        parser.add_argument("linters", nargs="*", type=str)

    def handle(self, *args, **options):
        try:
            errors = []
            for linter in self.linters.values():
                self.stdout.write(f"[manage.py lint] {linter['purpose']}. . .")
                result = run(linter["args"])  # nosec
                if result.returncode:
                    self.stderr.write(
                        self.style.NOTICE(
                            "[manage.py lint] Re-try with: [docker-compose exec app] " f"{' '.join(linter['args'])}"
                        )
                    )
                    errors.append(CalledProcessError(result.returncode, linter["args"]))
                else:
                    self.stdout.write(f"[manage.py lint] {linter['purpose']} completed with success!")
            if errors:
                self.stdout.write(f"[manage.py lint] {len(errors)} linter(s) failed.")
                raise LinterError(errors)
        except (CalledProcessError, LinterError) as e:
            raise CommandError(e)
        self.stdout.write(self.style.SUCCESS("[manage.py lint] All linters ran successfully."))
