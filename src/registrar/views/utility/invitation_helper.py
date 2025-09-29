from django.contrib import messages
from django.db import IntegrityError
from registrar.models import PortfolioInvitation, User, UserPortfolioPermission
from registrar.utility.email import EmailSendingError
import logging
from registrar.utility.errors import (
    AlreadyDomainInvitedError,
    AlreadyDomainManagerError,
    MissingEmailError,
    OutsideOrgMemberError,
)
from django.utils.html import format_html

logger = logging.getLogger(__name__)

# These methods are used by multiple views which share similar logic and function
# when creating invitations and sending associated emails. These can be reused in
# any view, and were initially developed for domain.py, portfolios.py and admin.py


def get_org_membership(org, email, user):
    """
    Determines if an email/user belongs to a different organization or this organization
    as either a member or an invited member.

    This function returns a tuple (member_of_a_different_org, member_of_this_org),
    which provides:
    - member_of_a_different_org: True if the user/email is associated with an organization other than the given org.
    - member_of_this_org: True if the user/email is associated with the given org.

    Note: This implementation assumes single portfolio ownership for a user.
    If the "multiple portfolios" feature is enabled, this logic may not account for
    situations where a user or email belongs to multiple organizations.
    """

    # Check for existing permissions or invitations for the user
    existing_org_permission = UserPortfolioPermission.objects.filter(user=user).first()
    existing_org_invitation = PortfolioInvitation.objects.filter(email=email).first()

    # Determine membership in a different organization
    member_of_a_different_org = (existing_org_permission and existing_org_permission.portfolio != org) or (
        existing_org_invitation and existing_org_invitation.portfolio != org
    )

    # Determine membership in the same organization
    member_of_this_org = (existing_org_permission and existing_org_permission.portfolio == org) or (
        existing_org_invitation and existing_org_invitation.portfolio == org
    )

    return member_of_a_different_org, member_of_this_org


def get_requested_user(email):
    """Retrieve a user by email or return None if the user doesn't exist."""
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        return None


def handle_invitation_exceptions(request, exception, email):
    """Handle exceptions raised during the process."""
    if isinstance(exception, EmailSendingError):
        logger.warning(exception, exc_info=True)
        messages.error(request, with_contact_link(str(exception)))
    elif isinstance(exception, MissingEmailError):
        messages.error(request, str(exception))
        logger.error(exception, exc_info=True)
    elif isinstance(exception, OutsideOrgMemberError):
        messages.error(request, str(exception))
    elif isinstance(exception, AlreadyDomainManagerError):
        messages.error(request, with_contact_link(str(exception)))
    elif isinstance(exception, AlreadyDomainInvitedError):
        messages.error(request, str(exception))
    elif isinstance(exception, IntegrityError):
        messages.error(request, f"{email} is already a manager for this domain")
    else:
        logger.warning("Could not send email invitation (Other Exception)", exc_info=True)
        messages.error(
            request, with_contact_link(f"An unexpected error occurred: {email} could not be added to this domain.")
        )


def with_contact_link(error_message: str, contact_url: str = "https://get.gov/contact") -> str:
    return format_html(
        '{} Try again, and if the problem persists, <a href="{}" class="usa-link" target="_blank">contact us</a>.',
        error_message,
        contact_url,
    )
