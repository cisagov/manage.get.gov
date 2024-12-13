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


def _is_member_of_different_org(email, requestor, requested_user):
    """Verifies if an email belongs to a different organization as a member or invited member."""
    # Check if requested_user is a already member of a different organization than the requestor's org
    requestor_org = UserPortfolioPermission.objects.filter(user=requestor).first().portfolio
    existing_org_permission = UserPortfolioPermission.objects.filter(user=requested_user).first()
    existing_org_invitation = PortfolioInvitation.objects.filter(email=email).first()

    return (existing_org_permission and existing_org_permission.portfolio != requestor_org) or (
        existing_org_invitation and existing_org_invitation.portfolio != requestor_org
    )


def send_domain_invitation_email(email: str, requestor, domain, requested_user=None):
    """
    Sends a domain invitation email to the specified address.

    Raises exceptions for validation or email-sending issues.

    Args:
        email (str): Email address of the recipient.
        requestor (User): The user initiating the invitation.
        domain (Domain): The domain object for which the invitation is being sent.
        requested_user (User): The user of the recipient, if exists; defaults to None

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
    if flag_is_active_for_user(requestor, "organization_feature") and _is_member_of_different_org(
        email, requestor, requested_user
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
    try:
        send_templated_email(
            "emails/domain_invitation.txt",
            "emails/domain_invitation_subject.txt",
            to_address=email,
            context={
                "domain": domain,
                "requestor_email": requestor_email,
            },
        )
    except EmailSendingError as exc:
        logger.warning(
            "Could not send email invitation to %s for domain %s",
            email,
            domain,
            exc_info=True,
        )
        raise EmailSendingError("Could not send email invitation.") from exc


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

    try:
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
    except EmailSendingError as exc:
        logger.warning(
            "Could not sent email invitation to %s for portfolio %s",
            email,
            portfolio,
            exc_info=True,
        )
        raise EmailSendingError("Could not send email invitation.") from exc

