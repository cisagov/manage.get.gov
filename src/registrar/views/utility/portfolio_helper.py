from django.contrib import messages
from django.db import IntegrityError
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user import User
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.utility.email import EmailSendingError
import logging

from registrar.utility.errors import (
    AlreadyDomainInvitedError,
    AlreadyDomainManagerError,
    MissingEmailError,
    OutsideOrgMemberError,
)

logger = logging.getLogger(__name__)


def get_org_membership(requestor_org, requested_email, requested_user):
    """
    Verifies if an email belongs to a different organization as a member or invited member.
    Verifies if an email belongs to this organization as a member or invited member.
    User does not belong to any org can be deduced from the tuple returned.

    Returns a tuple (member_of_a_different_org, member_of_this_org).
    """

    # COMMENT: this code does not take into account multiple portfolios flag

    # COMMENT: shouldn't this code be based on the organization of the domain, not the org
    # of the requestor? requestor could have multiple portfolios

    # Check for existing permissions or invitations for the requested user
    existing_org_permission = UserPortfolioPermission.objects.filter(user=requested_user).first()
    existing_org_invitation = PortfolioInvitation.objects.filter(email=requested_email).first()

    # Determine membership in a different organization
    member_of_a_different_org = (existing_org_permission and existing_org_permission.portfolio != requestor_org) or (
        existing_org_invitation and existing_org_invitation.portfolio != requestor_org
    )

    # Determine membership in the same organization
    member_of_this_org = (existing_org_permission and existing_org_permission.portfolio == requestor_org) or (
        existing_org_invitation and existing_org_invitation.portfolio == requestor_org
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
        logger.warning(str(exception), exc_info=True)
        messages.error(request, str(exception))
    elif isinstance(exception, MissingEmailError):
        messages.error(request, str(exception))
        logger.error(str(exception), exc_info=True)
    elif isinstance(exception, OutsideOrgMemberError):
        logger.warning(
            "Could not send email. Can not invite member of a .gov organization to a different organization.",
            exc_info=True,
        )
        messages.error(
            request,
            f"{email} is already a member of another .gov organization.",
        )
    elif isinstance(exception, AlreadyDomainManagerError):
        messages.warning(request, str(exception))
    elif isinstance(exception, AlreadyDomainInvitedError):
        messages.warning(request, str(exception))
    elif isinstance(exception, IntegrityError):
        messages.warning(request, f"{email} is already a manager for this domain")
    else:
        logger.warning("Could not send email invitation (Other Exception)", exc_info=True)
        messages.warning(request, "Could not send email invitation.")
