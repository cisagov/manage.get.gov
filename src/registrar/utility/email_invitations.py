from datetime import date
from django.conf import settings
from registrar.models import Domain, DomainInvitation, UserDomainRole, DomainInformation
from registrar.models.portfolio import Portfolio
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user import User
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


def _normalize_domains(domains: Domain | list[Domain]) -> list[Domain]:
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
    _check_outside_org_membership(email, requestor, is_member_of_different_org)

    for domain in domains:
        _validate_existing_invitation(email, user, domain)

        # NOTE: should we also be validating against existing user_domain_roles


def _check_outside_org_membership(email, requestor, is_member_of_different_org):
    """Raise an error if the email belongs to a different organization."""
    if not flag_is_active_for_user(requestor, "multiple_portfolios") and is_member_of_different_org:
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


def _send_domain_invitation_email(email, requestor_email, domains, requested_user):
    """Send the invitation email."""
    try:
        send_templated_email(
            "emails/domain_invitation.txt",
            "emails/domain_invitation_subject.txt",
            to_addresses=email,
            context={
                "domains": domains,
                "requestor_email": requestor_email,
                "invitee_email_address": email,
                "requested_user": requested_user,
            },
        )
    except EmailSendingError as err:
        domain_names = ", ".join([domain.name for domain in domains])
        logger.error(
            "Failed to send domain invitation email:\n"
            f"  Requestor Email: {requestor_email}\n"
            f"  Subject template: domain_invitation_subject.txt\n"
            f"  To: {email}\n"
            f"  Domains: {domain_names}\n"
            f"  Error: {err}",
            exc_info=True,
        )
        raise EmailSendingError(f"An unexpected error occurred: {email} could not be added to this domain.") from err


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
    domains = _normalize_domains(domains)
    requestor_email = _get_requestor_email(requestor, domains=domains)

    _validate_invitation(email, requested_user, domains, requestor, is_member_of_different_org)

    _send_domain_invitation_email(email, requestor_email, domains, requested_user)

    all_manager_emails_sent = True
    # send emails to domain managers
    for domain in domains:
        if not _send_domain_invitation_update_emails_to_domain_managers(
            email=email,
            requestor_email=requestor_email,
            domain=domain,
            requested_user=requested_user,
        ):
            all_manager_emails_sent = False

    return all_manager_emails_sent


def _send_domain_invitation_update_emails_to_domain_managers(
    email: str, requestor_email, domain: Domain, requested_user=None
):
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
        if not user:
            continue
        try:
            send_templated_email(
                "emails/domain_manager_notification.txt",
                "emails/domain_manager_notification_subject.txt",
                to_addresses=[user.email],
                context={
                    "domain": domain,
                    "requestor_email": requestor_email,
                    "invited_email_address": email,
                    "domain_manager": user,
                    "date": date.today(),
                },
            )
        except EmailSendingError as err:
            logger.error(
                "Failed to send domain manager update notification email:\n"
                f"  Requestor Email: {requestor_email}\n"
                f"  Subject: domain_manager_notification_subject.txt\n"
                f"  To: {user.email}\n"
                f"  Domain: {domain.name}\n"
                f"  Error: {err}",
                exc_info=True,
            )
            all_emails_sent = False
    return all_emails_sent


def send_domain_manager_removal_emails_to_domain_managers(
    removed_by_user: User,
    manager_removed: User,
    manager_removed_email: str,
    domain: Domain,
):
    """
    Notifies all domain managers that a domain manager has been removed.

    Args:
        removed_by_user(User): The user who initiated the removal.
        manager_removed(User): The user being removed.
        manager_removed_email(str): The email of the user being removed (in case no User).
        domain(Domain): The domain the user is being removed from.

    Returns:
        Boolean indicating if all messages were sent successfully.

    """
    all_emails_sent = True
    # Get each domain manager from list (exclude pending invitations where user is null)
    user_domain_roles = UserDomainRole.objects.filter(domain=domain)
    if manager_removed:
        user_domain_roles = user_domain_roles.exclude(user=manager_removed)
    for user_domain_role in user_domain_roles:
        # Send email to each domain manager
        user = user_domain_role.user
        if not user:
            continue
        try:
            send_templated_email(
                "emails/domain_manager_deleted_notification.txt",
                "emails/domain_manager_deleted_notification_subject.txt",
                to_addresses=[user.email],
                context={
                    "domain": domain,
                    "removed_by": removed_by_user,
                    "manager_removed_email": manager_removed_email,
                    "date": date.today(),
                },
            )
        except EmailSendingError as err:
            logger.error(
                "Failed to send domain manager deleted notification email:\n"
                f"  User that did the removing: {removed_by_user}\n"
                f"  Domain manager removed: {manager_removed_email}\n"
                f"  Subject template: domain_manager_deleted_notification_subject.txt\n"
                f"  To: {user.email}\n"
                f"  Domain: {domain.name}\n"
                f"  Error: {err}",
                exc_info=True,
            )
            all_emails_sent = False
    return all_emails_sent


def send_domain_manager_on_hold_email_to_domain_managers(domain: Domain, requestor):
    """
    Notifies all domain managers that a domain they are a domain manager
    for has been put on hold and set to be deleted in 7 days.

    Args:
        domain (Domain): The domain that is going to be put on hold
        requestor (User): The user initiating the request to delete the domain

    Returns:
        Boolean indicating if all messages were sent successfully.

    """
    all_emails_sent = True
    # Get domain manager emails
    domain_manager_emails = list(
        UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct()
    )
    requestor_email = _get_requestor_email(requestor, domains=domain)

    bcc_address = settings.DEFAULT_FROM_EMAIL if settings.IS_PRODUCTION else ""
    try:
        send_templated_email(
            "emails/domain_on_hold_notification.txt",
            "emails/domain_on_hold_notification_subject.txt",
            to_addresses=domain_manager_emails,
            bcc_address=bcc_address,
            context={
                "domain": domain,
                "requestor_email": requestor_email,
                "date": date.today(),
            },
        )
    except EmailSendingError as err:
        logger.error(
            "Failed to send domain manager deleted notification email:\n"
            f"  Subject template: domain_on_hold_notification_subject.txt\n"
            f"  To: {domain_manager_emails}\n"
            f"  Domain: {domain.name}\n"
            f"  Error: {err}",
            exc_info=True,
        )
        all_emails_sent = False
    return all_emails_sent


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
            to_addresses=[email],
            context={
                "portfolio": portfolio,
                "requestor_email": requestor_email,
                "email": email,
            },
        )
    except EmailSendingError as err:
        logger.error(
            "Failed to send portfolio invitation email:\n"
            f"  Requestor Email: {requestor_email}\n"
            f"  Subject template: portfolio_invitation_subject.txt\n"
            f"  To: {email}\n"
            f"  Portfolio: {portfolio}\n"
            f"  Error: {err}",
            exc_info=True,
        )
        raise EmailSendingError(f"An unexpected error occurred: {email} could not be added to this domain.") from err

    all_admin_emails_sent = True
    # send emails to portfolio admins
    if is_admin_invitation:
        all_admin_emails_sent = _send_portfolio_admin_addition_emails_to_portfolio_admins(
            email=email,
            requestor_email=requestor_email,
            portfolio=portfolio,
        )
    return all_admin_emails_sent


def send_portfolio_update_emails_to_portfolio_admins(editor, portfolio, updated_page):
    """
    Sends an email notification to all portfolio admin when portfolio organization is updated.

    Raises exceptions for validation or email-sending issues.

    Args:
        editor (User): The user editing the portfolio organization.
        portfolio (Portfolio): The portfolio object whose organization information is changed.

    Returns:
        Boolean indicating if all messages were sent successfully.

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
        EmailSendingError: If there is an error while sending the email.
    """
    all_emails_sent = True
    # Get each portfolio admin from list
    user_portfolio_permissions = UserPortfolioPermission.objects.filter(
        portfolio=portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
    )
    for user_portfolio_permission in user_portfolio_permissions:
        # Send email to each portfolio_admin
        user = user_portfolio_permission.user
        if not user:
            continue
        try:
            send_templated_email(
                "emails/portfolio_org_update_notification.txt",
                "emails/portfolio_org_update_notification_subject.txt",
                to_addresses=user.email,
                context={
                    "requested_user": user,
                    "portfolio": portfolio,
                    "editor": editor,
                    "portfolio_admin": user,
                    "date": date.today(),
                    "updated_info": updated_page,
                },
            )
        except EmailSendingError as err:
            logger.error(
                "Failed to send portfolio org update notification email:\n"
                f"  Requested User: {user}\n"
                f"  Subject template: portfolio_org_update_notification_subject.txt\n"
                f"  To: {user.email}\n"
                f"  Portfolio: {portfolio}\n"
                f"  Error: {err}",
                exc_info=True,
            )
            all_emails_sent = False
    return all_emails_sent


def send_portfolio_member_permission_update_email(requestor, permissions: UserPortfolioPermission):
    """
    Sends an email notification to a portfolio member when their permissions are updated.

    This function retrieves the requestor's email and sends a templated email to the affected user,
    notifying them of changes to their portfolio permissions.

    Args:
        requestor (User): The user initiating the permission update.
        permissions (UserPortfolioPermission): The updated permissions object containing the affected user
                                              and the portfolio details.

    Returns:
        bool: True if the email was sent successfully, False if an EmailSendingError occurred.

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
    """
    # Exclude pending invitations where user is null
    if not permissions.user:
        return False
    requestor_email = _get_requestor_email(requestor, portfolio=permissions.portfolio)
    try:
        send_templated_email(
            "emails/portfolio_update.txt",
            "emails/portfolio_update_subject.txt",
            to_addresses=[permissions.user.email],
            context={
                "requested_user": permissions.user,
                "portfolio": permissions.portfolio,
                "requestor_email": requestor_email,
                "permissions": permissions,
                "date": date.today(),
            },
        )
    except EmailSendingError as err:
        logger.error(
            "Failed to send organization member update notification email:\n"
            f"  Requestor Email: {requestor_email}\n"
            f"  Subject template: portfolio_update_subject.txt\n"
            f"  To: {permissions.user.email}\n"
            f"  Portfolio: {permissions.portfolio}\n"
            f"  Error: {err}",
            exc_info=True,
        )
        return False
    return True


def send_portfolio_member_permission_remove_email(requestor, permissions: UserPortfolioPermission):
    """
    Sends an email notification to a portfolio member when their permissions are deleted.

    This function retrieves the requestor's email and sends a templated email to the affected user,
    notifying them of the removal of their portfolio permissions.

    Args:
        requestor (User): The user initiating the permission update.
        permissions (UserPortfolioPermission): The updated permissions object containing the affected user
                                              and the portfolio details.

    Returns:
        bool: True if the email was sent successfully, False if an EmailSendingError occurred.

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
    """
    # Exclude pending invitations where user is null
    if not permissions.user:
        return False
    requestor_email = _get_requestor_email(requestor, portfolio=permissions.portfolio)
    try:
        send_templated_email(
            "emails/portfolio_removal.txt",
            "emails/portfolio_removal_subject.txt",
            to_addresses=[permissions.user.email],
            context={
                "requested_user": permissions.user,
                "portfolio": permissions.portfolio,
                "requestor_email": requestor_email,
            },
        )
    except EmailSendingError as err:
        logger.error(
            "Failed to send portfolio member removal email:\n"
            f"  Requestor Email: {requestor_email}\n"
            f"  Subject template: portfolio_removal_subject.txt\n"
            f"  To: {permissions.user.email}\n"
            f"  Portfolio: {permissions.portfolio}\n"
            f"  Error: {err}",
            exc_info=True,
        )
        return False
    return True


def send_portfolio_invitation_remove_email(requestor, invitation: PortfolioInvitation):
    """
    Sends an email notification to a portfolio invited member when their permissions are deleted.

    This function retrieves the requestor's email and sends a templated email to the affected email,
    notifying them of the removal of their invited portfolio permissions.

    Args:
        requestor (User): The user initiating the permission update.
        invitation (PortfolioInvitation): The invitation object containing the affected user
                                              and the portfolio details.

    Returns:
        bool: True if the email was sent successfully, False if an EmailSendingError occurred.

    Raises:
        MissingEmailError: If the requestor has no email associated with their account.
    """
    requestor_email = _get_requestor_email(requestor, portfolio=invitation.portfolio)
    try:
        send_templated_email(
            "emails/portfolio_removal.txt",
            "emails/portfolio_removal_subject.txt",
            to_addresses=[invitation.email],
            context={
                "requested_user": None,
                "portfolio": invitation.portfolio,
                "requestor_email": requestor_email,
            },
        )
    except EmailSendingError as err:
        logger.error(
            "Failed to send portfolio invitation removal email:\n"
            f"  Subject template: portfolio_removal_subject.txt\n"
            f"  To: {invitation.email}\n"
            f"  Portfolio: {invitation.portfolio.organization_name}\n"
            f"  Error: {err}",
            exc_info=True,
        )
        return False
    return True


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
        if not user:
            continue
        try:
            send_templated_email(
                "emails/portfolio_admin_addition_notification.txt",
                "emails/portfolio_admin_addition_notification_subject.txt",
                to_addresses=[user.email],
                context={
                    "portfolio": portfolio,
                    "requestor_email": requestor_email,
                    "invited_email_address": email,
                    "portfolio_admin": user,
                    "date": date.today(),
                },
            )
        except EmailSendingError as err:
            logger.error(
                "Failed to send portfolio admin addition notification email:\n"
                f"  Requestor Email: {requestor_email}\n"
                f"  Subject template: portfolio_admin_addition_notification_subject.txt\n"
                f"  To: {user.email}\n"
                f"  Portfolio: {portfolio}\n"
                f"  Portfolio Admin: {user}\n"
                f"  Error: {err}",
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
        if not user:
            continue
        try:
            send_templated_email(
                "emails/portfolio_admin_removal_notification.txt",
                "emails/portfolio_admin_removal_notification_subject.txt",
                to_addresses=[user.email],
                context={
                    "portfolio": portfolio,
                    "requestor_email": requestor_email,
                    "removed_email_address": email,
                    "portfolio_admin": user,
                    "date": date.today(),
                },
            )
        except EmailSendingError as err:
            logger.error(
                "Failed to send portfolio admin removal notification email:\n"
                f"  Requestor Email: {requestor_email}\n"
                f"  Subject template: portfolio_admin_removal_notification_subject.txt\n"
                f"  To: {user.email}\n"
                f"  Portfolio: {portfolio.organization_name}\n"
                f"  Error: {err}",
                exc_info=True,
            )
            all_emails_sent = False
    return all_emails_sent


def send_domain_renewal_notification_emails(domain: Domain):
    """
    Notifies domain managers and organization admins when a domain has been renewed
    Args:
       domain: The Domain object that has been renewed

    Returns:
    Boolean indicating if all messages were sent successfully.
    """

    all_emails_sent = True

    context = {"domain": domain, "expiration_date": domain.expiration_date}

    # Get all the domain manager for this domain
    domain_manager_emails = list(
        UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct()
    )

    # Get organization admins if the domain belongs to a portfolio
    domain_info = DomainInformation.objects.filter(domain=domain).first()
    portfolio = getattr(domain_info, "portfolio", None)
    org_admins_emails = []

    if portfolio:
        emails = list(portfolio.portfolio_admin_users.values_list("email", flat=True).distinct())
        org_admins_emails.extend(emails)

    try:
        send_templated_email(
            template_name="emails/domain_renewal_success.txt",
            subject_template_name="emails/domain_renewal_success_subject.txt",
            to_addresses=domain_manager_emails,
            cc_addresses=org_admins_emails,
            context=context,
        )
    except EmailSendingError as err:
        logger.error(
            "Failed to send domain renewal:\n "
            f"Subject template: emails/domain_renewal_success_subject.txt\n"
            f"Domain: {domain.name}"
            f"To addresses: {domain_manager_emails}"
            f"CC addresses: {org_admins_emails}"
            f"Error: {err}"
        )
        all_emails_sent = False

    return all_emails_sent

def send_domain_deletion_emails_for_dns_needed_and_unknown_to_domain_managers(domains):
    all_emails_sent = True
    subject_txt = "emails/domain_deletion_dns_needed_unknown_subject.txt"
    body_txt = "emails/domain_deletion_dns_needed_unknown_body.txt"
    for domain in domains:
        user_domain_roles_emails = list(UserDomainRole.objects.filter(domain=domain).values_list("user__email", flat=True).distinct())

        try:
            send_templated_email(
                body_txt,
                subject_txt,
                to_addresses=user_domain_roles_emails,
                context={"domain": domain, "date_of_deletion": domain.deleted.date() }
            )
        except EmailSendingError as err:
            logger.error(
                "Failed to send domain deletion domain manager emails"
                f"Subject template: domain_deletion_dns_needed_unknown_subject.txt"
                f"To: {user_domain_roles_emails}"
                f"Domain: {domain.name}"
                f"Error: {err}"
            )
            all_emails_sent = False
    return all_emails_sent