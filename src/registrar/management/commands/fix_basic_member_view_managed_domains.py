"""
Management command to ensure all existing ORGANIZATION_MEMBER users
have VIEW_MANAGED_DOMAINS permission.
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from registrar.models import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices, UserPortfolioPermissionChoices

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Ensures all ORGANIZATION_MEMBER users have VIEW_MANAGED_DOMAINS permission.
    This fixes the issue where basic members cannot see domains they manage.
    This command is safe to run multiple times and will only update users who need it.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry_run", action="store_true", help="Show what would be changed without making modifications"
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Show detailed information about each user processed"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made\n"))

        # Find all ORGANIZATION_MEMBER users who don't have VIEW_MANAGED_DOMAINS permission
        # and who actually manage domains (to avoid unnecessary updates)
        members_without_permission = self._find_members_needing_permission()

        total_to_update = members_without_permission.count()
        self.stdout.write(f"Found {total_to_update} basic members who need VIEW_MANAGED_DOMAINS permission")

        if total_to_update == 0:
            self.stdout.write(self.style.SUCCESS("All basic members already have the necessary permissions."))
            return

        # Show some examples if verbose
        if verbose and total_to_update > 0:
            self.stdout.write("\nExamples of users who will be updated:")
            for perm in members_without_permission[:5]:
                managed_count = perm.get_managed_domains_count()
                self.stdout.write(
                    f"  • {perm.user.email} in '{perm.portfolio.organization_name}' "
                    f"(manages {managed_count} domains)"
                )
            if total_to_update > 5:
                self.stdout.write(f"  ... and {total_to_update - 5} more")
            self.stdout.write("")

        if not dry_run:
            confirm = input("Do you want to proceed with updating these users? (y/N): ")
            if confirm.lower() != "y":
                self.stdout.write("Aborted.")
                return

        updated_count = self._update_permissions(members_without_permission, dry_run, verbose)

        action = "Would update" if dry_run else "Successfully updated"
        self.stdout.write(self.style.SUCCESS(f"{action} {updated_count} user permissions"))

        if not dry_run:
            self.stdout.write("\n🎉 Fix complete! Basic members should now be able to view domains they manage.")

    def _find_members_needing_permission(self):
        """Find ORGANIZATION_MEMBER users who need VIEW_MANAGED_DOMAINS permission."""
        return (
            UserPortfolioPermission.objects.filter(
                # Must be an org member
                roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
            )
            .exclude(
                # Exclude those who already have the permission
                additional_permissions__contains=[UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS]
            )
            .distinct()
        )

    def _update_permissions(self, permissions_to_update, dry_run, verbose):
        """Update the permissions for the given users."""
        updated_count = 0

        with transaction.atomic():
            for permission in permissions_to_update:
                # Get current additional permissions or initialize as empty list
                current_perms = permission.additional_permissions or []

                # Add VIEW_MANAGED_DOMAINS if not already present
                if UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS not in current_perms:
                    new_perms = current_perms + [UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS]

                    if not dry_run:
                        permission.additional_permissions = new_perms
                        permission.save()

                    if verbose:
                        managed_count = permission.get_managed_domains_count()
                        action = "WOULD UPDATE" if dry_run else "UPDATED"
                        self.stdout.write(
                            f"  {action}: {permission.user.email} in "
                            f"'{permission.portfolio.organization_name}' "
                            f"(manages {managed_count} domains)"
                        )

                    updated_count += 1

        return updated_count
