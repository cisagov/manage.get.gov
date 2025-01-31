from datetime import date
from django.conf import settings
from registrar.models import Domain, DomainInvitation, UserDomainRole
from registrar.models.portfolio import Portfolio
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
from registrar.utility.errors import (
    AlreadyDomainInvitedError,
    AlreadyDomainManagerError,
    MissingEmailError,
    OutsideOrgMemberError,
)
from registrar.utility.waffle import flag_is_active_for_user
from registrar.utility.email import EmailSendingError, send_templated_email
import logging

logger = logging.getLogger(__name__)


def send_domain_invitation_email(
    email: str, requestor, domains: Domain | list[Domain], is_member_of_different_org, requested_user=None
):
    """
    Sends a domain invitation email to the specified address.

    Args:
        email (str): Email address of the recipient.
        requestor (User): The user initiating the invitation.
        domains (Domain or list of Domain): The domain objects for which the invitation is being sent.
        is_member_of_different_org (bool): if an email belongs to a different org
        requested_user (User | None): The recipient if the email belongs to a user in the registrar

    Returns:
        Boolean indicating if all messages were sent successfully.

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
        AlreadyDomainManagerError: If the email corresponds to an existing domain manager.
        AlreadyDomainInvitedError: If an invitation has already been sent.
        OutsideOrgMemberError: If the requested_user is part of a different organization.
        EmailSendingError: If there is an error while sending the email.
    """
    domains = normalize_domains(domains)
    requestor_email = _get_requestor_email(requestor, domains=domains)

    _validate_invitation(email, requested_user, domains, requestor, is_member_of_different_org)

    send_invitation_email(email, requestor_email, domains, requested_user)

    all_manager_emails_sent = True
    # send emails to domain managers
    for domain in domains:
        if not send_emails_to_domain_managers(
            email=email,
            requestor_email=requestor_email,
            domain=domain,
            requested_user=requested_user,
        ):
            all_manager_emails_sent = False

    return all_manager_emails_sent


def send_emails_to_domain_managers(email: str, requestor_email, domain: Domain, requested_user=None):
    """
    Notifies all domain managers of the provided domain of a change

    Returns:
        Boolean indicating if all messages were sent successfully.
    """
    all_emails_sent = True
    # Get each domain manager from list
    user_domain_roles = UserDomainRole.objects.filter(domain=domain)
    for user_domain_role in user_domain_roles:
        # Send email to each domain manager
        user = user_domain_role.user
        try:
            send_templated_email(
                "emails/domain_manager_notification.txt",
                "emails/domain_manager_notification_subject.txt",
                to_address=user.email,
                context={
                    "domain": domain,
                    "requestor_email": requestor_email,
                    "invited_email_address": email,
                    "domain_manager": user,
                    "date": date.today(),
                },
            )
        except EmailSendingError:
            logger.warning(
                f"Could not send email manager notification to {user.email} for domain: {domain.name}", exc_info=True
            )
            all_emails_sent = False
    return all_emails_sent


def normalize_domains(domains: Domain | list[Domain]) -> list[Domain]:
    """Ensures domains is always a list."""
    return [domains] if isinstance(domains, Domain) else domains


def _get_requestor_email(requestor, domains=None, portfolio=None):
    """Get the requestor's email or raise an error if it's missing.

    If the requestor is staff, default email is returned.

    Raises:
        MissingEmailError
    """
    if requestor.is_staff:
        return settings.DEFAULT_FROM_EMAIL

    if not requestor.email or requestor.email.strip() == "":
        domain_names = None
        if domains:
            domain_names = ", ".join([domain.name for domain in domains])
        raise MissingEmailError(email=requestor.email, domain=domain_names, portfolio=portfolio)

    return requestor.email


def _validate_invitation(email, user, domains, requestor, is_member_of_different_org):
    """Validate the invitation conditions."""
    check_outside_org_membership(email, requestor, is_member_of_different_org)

    for domain in domains:
        _validate_existing_invitation(email, user, domain)

        # NOTE: should we also be validating against existing user_domain_roles


def check_outside_org_membership(email, requestor, is_member_of_different_org):
    """Raise an error if the email belongs to a different organization."""
    if (
        flag_is_active_for_user(requestor, "organization_feature")
        and not flag_is_active_for_user(requestor, "multiple_portfolios")
        and is_member_of_different_org
    ):
        raise OutsideOrgMemberError(email=email)


def _validate_existing_invitation(email, user, domain):
    """Check for existing invitations and handle their status."""
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
    if user:
        if UserDomainRole.objects.filter(user=user, domain=domain).exists():
            raise AlreadyDomainManagerError(email)


def send_invitation_email(email, requestor_email, domains, requested_user):
    """Send the invitation email."""
    try:
        send_templated_email(
            "emails/domain_invitation.txt",
            "emails/domain_invitation_subject.txt",
            to_address=email,
            context={
                "domains": domains,
                "requestor_email": requestor_email,
                "invitee_email_address": email,
                "requested_user": requested_user,
            },
        )
    except EmailSendingError as err:
        domain_names = ", ".join([domain.name for domain in domains])
        raise EmailSendingError(f"Could not send email invitation to {email} for domains: {domain_names}") from err


def send_portfolio_invitation_email(email: str, requestor, portfolio, is_admin_invitation):
    """
    Sends a portfolio member invitation email to the specified address.

    Raises exceptions for validation or email-sending issues.

    Args:
        email (str): Email address of the recipient
        requestor (User): The user initiating the invitation.
        portfolio (Portfolio): The portfolio object for which the invitation is being sent.
        is_admin_invitation (boolean): boolean indicating if the invitation is an admin invitation

    Returns:
        Boolean indicating if all messages were sent successfully.

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
        EmailSendingError: If there is an error while sending the email.
    """

    requestor_email = _get_requestor_email(requestor, portfolio=portfolio)

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
    except EmailSendingError as err:
        raise EmailSendingError(
            f"Could not sent email invitation to {email} for portfolio {portfolio}. Portfolio invitation not saved."
        ) from err

    all_admin_emails_sent = True
    # send emails to portfolio admins
    if is_admin_invitation:
        all_admin_emails_sent = _send_portfolio_admin_addition_emails_to_portfolio_admins(
            email=email,
            requestor_email=requestor_email,
            portfolio=portfolio,
        )
    return all_admin_emails_sent


def send_portfolio_admin_addition_emails(email: str, requestor, portfolio: Portfolio):
    """
    Notifies all portfolio admins of the provided portfolio of a newly invited portfolio admin

    Returns:
        Boolean indicating if all messages were sent successfully.

    Raises:
        MissingEmailError
    """
    requestor_email = _get_requestor_email(requestor, portfolio=portfolio)
    return _send_portfolio_admin_addition_emails_to_portfolio_admins(email, requestor_email, portfolio)


def _send_portfolio_admin_addition_emails_to_portfolio_admins(email: str, requestor_email, portfolio: Portfolio):
    """
    Notifies all portfolio admins of the provided portfolio of a newly invited portfolio admin

    Returns:
        Boolean indicating if all messages were sent successfully.
    """
    all_emails_sent = True
    # Get each portfolio admin from list
    user_portfolio_permissions = UserPortfolioPermission.objects.filter(
        portfolio=portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
    ).exclude(user__email=email)
    for user_portfolio_permission in user_portfolio_permissions:
        # Send email to each portfolio_admin
        user = user_portfolio_permission.user
        try:
            send_templated_email(
                "emails/portfolio_admin_addition_notification.txt",
                "emails/portfolio_admin_addition_notification_subject.txt",
                to_address=user.email,
                context={
                    "portfolio": portfolio,
                    "requestor_email": requestor_email,
                    "invited_email_address": email,
                    "portfolio_admin": user,
                    "date": date.today(),
                },
            )
        except EmailSendingError:
            logger.warning(
                f"Could not send email organization admin notification to {user.email} for portfolio: {portfolio.name}",
                exc_info=True,
            )
            all_emails_sent = False
    return all_emails_sent


def send_portfolio_admin_removal_emails(email: str, requestor, portfolio: Portfolio):
    """
    Notifies all portfolio admins of the provided portfolio of a removed portfolio admin

    Returns:
        Boolean indicating if all messages were sent successfully.

    Raises:
        MissingEmailError
    """
    requestor_email = _get_requestor_email(requestor, portfolio=portfolio)
    return _send_portfolio_admin_removal_emails_to_portfolio_admins(email, requestor_email, portfolio)


def _send_portfolio_admin_removal_emails_to_portfolio_admins(email: str, requestor_email, portfolio: Portfolio):
    """
    Notifies all portfolio admins of the provided portfolio of a removed portfolio admin

    Returns:
        Boolean indicating if all messages were sent successfully.
    """
    all_emails_sent = True
    # Get each portfolio admin from list
    user_portfolio_permissions = UserPortfolioPermission.objects.filter(
        portfolio=portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
    ).exclude(user__email=email)
    for user_portfolio_permission in user_portfolio_permissions:
        # Send email to each portfolio_admin
        user = user_portfolio_permission.user
        try:
            send_templated_email(
                "emails/portfolio_admin_removal_notification.txt",
                "emails/portfolio_admin_removal_notification_subject.txt",
                to_address=user.email,
                context={
                    "portfolio": portfolio,
                    "requestor_email": requestor_email,
                    "removed_email_address": email,
                    "portfolio_admin": user,
                    "date": date.today(),
                },
            )
        except EmailSendingError:
            logger.warning(
                f"Could not send email organization admin notification to {user.email} for portfolio: {portfolio.name}",
                exc_info=True,
            )
            all_emails_sent = False
    return all_emails_sent
