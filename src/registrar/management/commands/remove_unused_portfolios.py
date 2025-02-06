import argparse
import logging

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db import transaction
from registrar.management.commands.utility.terminal_helper import (
    TerminalColors,
    TerminalHelper,
)
from registrar.models import (
    Portfolio,
    DomainGroup,
    DomainInformation,
    DomainRequest,
    PortfolioInvitation,
    Suborganization,
    UserPortfolioPermission,
)

logger = logging.getLogger(__name__)

ALLOWED_PORTFOLIOS = [
    "Department of Veterans Affairs",
    "Department of the Treasury",
    "National Archives and Records Administration",
    "Department of Defense",
    "Office of Personnel Management",
    "National Aeronautics and Space Administration",
    "City and County of San Francisco",
    "State of Arizona, Executive Branch",
    "Department of the Interior",
    "Department of State",
    "Department of Justice",
    "Capitol Police",
    "Administrative Office of the Courts",
    "Supreme Court of the United States",
]


class Command(BaseCommand):
    help = "Remove all Portfolio entries with names not in the allowed list."

    def add_arguments(self, parser):
        """
        OPTIONAL ARGUMENTS:
        --debug
        A boolean (default to true), which activates additional print statements
        """
        parser.add_argument("--debug", action=argparse.BooleanOptionalAction)

    def prompt_delete_entries(self, portfolios_to_delete, debug_on):
        """Brings up a prompt in the terminal asking
        if the user wishes to delete data in the
        Portfolio table.  If the user confirms,
        deletes the data in the Portfolio table"""

        entries_to_remove_by_name = list(portfolios_to_delete.values_list("organization_name", flat=True))
        formatted_entries = "\n\t\t".join(entries_to_remove_by_name)
        confirm_delete = TerminalHelper.query_yes_no(
            f"""
            {TerminalColors.FAIL}
            WARNING: You are about to delete the following portfolios:

                {formatted_entries}

            Are you sure you want to continue?{TerminalColors.ENDC}"""
        )
        if confirm_delete:
            logger.info(
                f"""{TerminalColors.YELLOW}
            ----------Deleting entries----------
            (please wait)
            {TerminalColors.ENDC}"""
            )
            self.delete_entries(portfolios_to_delete, debug_on)
        else:
            logger.info(
                f"""{TerminalColors.OKCYAN}
            ----------No entries deleted----------
            (exiting script)
            {TerminalColors.ENDC}"""
            )

    def delete_entries(self, portfolios_to_delete, debug_on):  # noqa: C901
        # Log the number of entries being removed
        count = portfolios_to_delete.count()
        if count == 0:
            logger.info(
                f"""{TerminalColors.OKCYAN}
                No entries to remove.
                {TerminalColors.ENDC}
                """
            )
            return

        # If debug mode is on, print out entries being removed
        if debug_on:
            entries_to_remove_by_name = list(portfolios_to_delete.values_list("organization_name", flat=True))
            formatted_entries = ", ".join(entries_to_remove_by_name)
            logger.info(
                f"""{TerminalColors.YELLOW}
                Entries to be removed: {formatted_entries}
                {TerminalColors.ENDC}
                """
            )

        # Check for portfolios with non-empty related objects
        # (These will throw integrity errors if they are not updated)
        portfolios_with_assignments = []
        for portfolio in portfolios_to_delete:
            has_assignments = any(
                [
                    DomainGroup.objects.filter(portfolio=portfolio).exists(),
                    DomainInformation.objects.filter(portfolio=portfolio).exists(),
                    DomainRequest.objects.filter(portfolio=portfolio).exists(),
                    PortfolioInvitation.objects.filter(portfolio=portfolio).exists(),
                    Suborganization.objects.filter(portfolio=portfolio).exists(),
                    UserPortfolioPermission.objects.filter(portfolio=portfolio).exists(),
                ]
            )
            if has_assignments:
                portfolios_with_assignments.append(portfolio)

        if portfolios_with_assignments:
            formatted_entries = "\n\t\t".join(
                f"{portfolio.organization_name}" for portfolio in portfolios_with_assignments
            )
            confirm_cascade_delete = TerminalHelper.query_yes_no(
                f"""
                {TerminalColors.FAIL}
                WARNING: these entries have related objects.

                    {formatted_entries}

                Deleting them will update any associated domains / domain requests to have no portfolio
                and will cascade delete any associated portfolio invitations, portfolio permissions, domain groups,
                and suborganizations.  Any suborganizations that get deleted will also orphan (not delete) their
                associated domains / domain requests.

                Are you sure you want to continue?{TerminalColors.ENDC}"""
            )
            if not confirm_cascade_delete:
                logger.info(
                    f"""{TerminalColors.OKCYAN}
                    Operation canceled by the user.
                    {TerminalColors.ENDC}
                    """
                )
                return

        # Try to delete the portfolios
        try:
            with transaction.atomic():
                summary = []
                for portfolio in portfolios_to_delete:
                    portfolio_summary = [f"---- CASCADE SUMMARY for {portfolio.organization_name} -----"]
                    if portfolio in portfolios_with_assignments:
                        domain_groups = DomainGroup.objects.filter(portfolio=portfolio)
                        domain_informations = DomainInformation.objects.filter(portfolio=portfolio)
                        domain_requests = DomainRequest.objects.filter(portfolio=portfolio)
                        portfolio_invitations = PortfolioInvitation.objects.filter(portfolio=portfolio)
                        suborganizations = Suborganization.objects.filter(portfolio=portfolio)
                        user_permissions = UserPortfolioPermission.objects.filter(portfolio=portfolio)

                        if domain_groups.exists():
                            formatted_groups = "\n".join([str(group) for group in domain_groups])
                            portfolio_summary.append(f"{len(domain_groups)} Deleted DomainGroups:\n{formatted_groups}")
                            domain_groups.delete()

                        if domain_informations.exists():
                            formatted_domain_infos = "\n".join([str(info) for info in domain_informations])
                            portfolio_summary.append(
                                f"{len(domain_informations)} Orphaned DomainInformations:\n{formatted_domain_infos}"
                            )
                            domain_informations.update(portfolio=None)

                        if domain_requests.exists():
                            formatted_domain_reqs = "\n".join([str(req) for req in domain_requests])
                            portfolio_summary.append(
                                f"{len(domain_requests)} Orphaned DomainRequests:\n{formatted_domain_reqs}"
                            )
                            domain_requests.update(portfolio=None)

                        if portfolio_invitations.exists():
                            formatted_portfolio_invitations = "\n".join([str(inv) for inv in portfolio_invitations])
                            portfolio_summary.append(
                                f"{len(portfolio_invitations)} Deleted PortfolioInvitations:\n{formatted_portfolio_invitations}"  # noqa
                            )
                            portfolio_invitations.delete()

                        if user_permissions.exists():
                            formatted_user_list = "\n".join(
                                [perm.user.get_formatted_name() for perm in user_permissions]
                            )
                            portfolio_summary.append(
                                f"Deleted UserPortfolioPermissions for the following users:\n{formatted_user_list}"
                            )
                            user_permissions.delete()

                        if suborganizations.exists():
                            portfolio_summary.append("Cascade Deleted Suborganizations:")
                            for suborg in suborganizations:
                                DomainInformation.objects.filter(sub_organization=suborg).update(sub_organization=None)
                                DomainRequest.objects.filter(sub_organization=suborg).update(sub_organization=None)
                                portfolio_summary.append(f"{suborg.name}")
                                suborg.delete()

                    portfolio.delete()
                    summary.append("\n\n".join(portfolio_summary))
                    summary_string = "\n\n".join(summary)

                # Output a success message with detailed summary
                logger.info(
                    f"""{TerminalColors.OKCYAN}
                    Successfully removed {count} portfolios.

                    The following portfolio deletions had cascading effects;

                    {summary_string}
                    {TerminalColors.ENDC}
                    """
                )

        except IntegrityError as e:
            logger.info(
                f"""{TerminalColors.FAIL}
                Could not delete some portfolios due to integrity constraints:
                {e}
                {TerminalColors.ENDC}
                """
            )

    def handle(self, *args, **options):
        # Get all Portfolio entries not in the allowed portfolios list
        portfolios_to_delete = Portfolio.objects.exclude(organization_name__in=ALLOWED_PORTFOLIOS)

        self.prompt_delete_entries(portfolios_to_delete, options.get("debug"))
