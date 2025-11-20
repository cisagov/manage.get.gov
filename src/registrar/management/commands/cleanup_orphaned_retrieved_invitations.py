import logging

from django.core.management import BaseCommand
from django.contrib.auth import get_user_model
from registrar.models import DomainInvitation, UserDomainRole

logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Cleans up orphaned retrieved domain invitations. "
        "An invitation is considered orphaned if it has status=RETRIEVED "
        "but there is no corresponding UserDomainRole for that user+domain combination."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print invitations that would be cleaned up without actually updating them",
        )

    def handle(self, *args, **options):
        """
        How to run it in dry run mode:
        ./manage.py cleanup_orphaned_retrieved_invitations --dry-run
        """
        dryrun = options.get("dry_run", False)

        # Find all retrieved invitations
        retrieved_invitations = DomainInvitation.objects.filter(
            status=DomainInvitation.DomainInvitationStatus.RETRIEVED
        )

        logger.info(f"Found {retrieved_invitations.count()} retrieved invitations to check")

        orphaned_count = 0
        cleaned_up_count = 0

        for invitation in retrieved_invitations:
            # Check if there's a corresponding UserDomainRole
            # We need to find the user by email (case-insensitive) and check if they have a role on this domain
            user_exists = User.objects.filter(email__iexact=invitation.email).exists()

            if not user_exists:
                # User doesn't exist anymore - this is orphaned
                orphaned_count += 1
                if dryrun:
                    logger.info(
                        f"[DRYRUN] Would cancel orphaned invitation: {invitation.email} on {invitation.domain.name} "
                        f"(user no longer exists)"
                    )
                else:
                    invitation.cancel_retrieved_invitation()
                    invitation.save()
                    logger.info(
                        f"Canceled orphaned invitation: {invitation.email} on {invitation.domain.name} "
                        f"(user no longer exists)"
                    )
                    cleaned_up_count += 1
                continue

            # User exists, check if they have a role on this domain
            user = User.objects.get(email__iexact=invitation.email)
            role_exists = UserDomainRole.objects.filter(
                user=user,
                domain=invitation.domain,
                role=UserDomainRole.Roles.MANAGER,
            ).exists()

            if not role_exists:
                # No role exists - this is orphaned
                orphaned_count += 1
                if dryrun:
                    logger.info(
                        f"[DRYRUN] Would cancel orphaned invitation: {invitation.email} on {invitation.domain.name} "
                        f"(no corresponding UserDomainRole)"
                    )
                else:
                    invitation.cancel_retrieved_invitation()
                    invitation.save()
                    logger.info(
                        f"Canceled orphaned invitation: {invitation.email} on {invitation.domain.name} "
                        f"(no corresponding UserDomainRole)"
                    )
                    cleaned_up_count += 1

        if dryrun:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRYRUN] Found {orphaned_count} orphaned retrieved invitations that would be cleaned up."
                )
            )
        else:
            if cleaned_up_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully cleaned up {cleaned_up_count} orphaned retrieved invitations.")
                )
            else:
                self.stdout.write(self.style.SUCCESS("No orphaned retrieved invitations found. Database is clean."))
