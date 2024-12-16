from django.conf import settings
from registrar.models import DomainInvitation
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.utility.errors import (
    AlreadyDomainInvitedError,
    AlreadyDomainManagerError,
    AlreadyPortfolioInvitedError,
    AlreadyPortfolioMemberError,
    MissingEmailError,
    OutsideOrgMemberError,
)
from registrar.utility.waffle import flag_is_active_for_user
from registrar.utility.email import send_templated_email, EmailSendingError
import logging

logger = logging.getLogger(__name__)


def send_domain_invitation_email(email: str, requestor, domain, is_member_of_different_org):
    """
    Sends a domain invitation email to the specified address.

    Raises exceptions for validation or email-sending issues.

    Args:
        email (str): Email address of the recipient.
        requestor (User): The user initiating the invitation.
        domain (Domain): The domain object for which the invitation is being sent.
        is_member_of_different_org (bool): if an email belongs to a different org

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
        AlreadyDomainManagerError: If the email corresponds to an existing domain manager.
        AlreadyDomainInvitedError: If an invitation has already been sent.
        OutsideOrgMemberError: If the requested_user is part of a different organization.
        EmailSendingError: If there is an error while sending the email.
    """
    # Default email address for staff
    requestor_email = settings.DEFAULT_FROM_EMAIL

    # Check if the requestor is staff and has an email
    if not requestor.is_staff:
        if not requestor.email or requestor.email.strip() == "":
            raise MissingEmailError(requestor.username)
        else:
            requestor_email = requestor.email

    # Check if the recipient is part of a different organization
    # COMMENT: this does not account for multiple_portfolios flag being active
    if (
        flag_is_active_for_user(requestor, "organization_feature")
        and not flag_is_active_for_user(requestor, "multiple_portfolios")
        and is_member_of_different_org
    ):
        raise OutsideOrgMemberError

    # Check for an existing invitation
    try:
        invite = DomainInvitation.objects.get(email=email, domain=domain)
        if invite.status == DomainInvitation.DomainInvitationStatus.RETRIEVED:
            raise AlreadyDomainManagerError(email)
        elif invite.status == DomainInvitation.DomainInvitationStatus.CANCELED:
            invite.update_cancellation_status()
            invite.save()
        else:
            raise AlreadyDomainInvitedError(email)
    except DomainInvitation.DoesNotExist:
        pass

    # Send the email
    send_templated_email(
        "emails/domain_invitation.txt",
        "emails/domain_invitation_subject.txt",
        to_address=email,
        context={
            "domain": domain,
            "requestor_email": requestor_email,
        },
    )


def send_portfolio_invitation_email(email: str, requestor, portfolio):
    """
    Sends a portfolio member invitation email to the specified address.

    Raises exceptions for validation or email-sending issues.

    Args:
        email (str): Email address of the recipient
        requestor (User): The user initiating the invitation.
        portfolio (Portfolio): The portfolio object for which the invitation is being sent.

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
        AlreadyPortfolioMemberError: If the email corresponds to an existing portfolio member.
        AlreadyPortfolioInvitedError: If an invitation has already been sent.
        EmailSendingError: If there is an error while sending the email.
    """

    # Default email address for staff
    requestor_email = settings.DEFAULT_FROM_EMAIL

    # Check if the requestor is staff and has an email
    if not requestor.is_staff:
        if not requestor.email or requestor.email.strip() == "":
            raise MissingEmailError(requestor.username)
        else:
            requestor_email = requestor.email

    # Check to see if an invite has already been sent
    try:
        invite = PortfolioInvitation.objects.get(email=email, portfolio=portfolio)
        if invite.status == PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED:
            raise AlreadyPortfolioMemberError(email)
        else:
            raise AlreadyPortfolioInvitedError(email)
    except PortfolioInvitation.DoesNotExist:
        pass

    send_templated_email(
        "emails/portfolio_invitation.txt",
        "emails/portfolio_invitation_subject.txt",
        to_address=email,
        context={
            "portfolio": portfolio,
            "requestor_email": requestor_email,
            "email": email,
        },
    )
