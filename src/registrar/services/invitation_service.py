import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from registrar.models import (
    Domain,
    DomainInvitation,
    Portfolio,
    PortfolioInvitation,
    User,
    UserDomainRole,
    UserPortfolioPermission,
)
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
from registrar.utility.email_invitations import (
    send_domain_invitation_email,
    send_portfolio_invitation_email,
)
from registrar.utility.errors import (
    AlreadyDomainInvitedError,
    AlreadyDomainManagerError,
    InvitationError,
)
from registrar.views.utility.invitation_helper import get_requested_user

logger = logging.getLogger(__name__)


def invite_to_portfolio(
    email: str,
    portfolio: Portfolio,
    requestor: User,
    roles: list,
    additional_permissions: list = None,
):
    """
    Invite a user to a portfolio.
    Creates invitation in new model (UserPortfolioPermission).

    Args:
        email: Email address of the invitee
        portfolio: Portfolio to invite user to
        requestor: User creating the invitation
        roles: List of portfolio roles
        additional_permissions: Optional list of additional permissions

    Returns:
        UserPortfolioPermission object

    Raises:
        InvitationError: If invitation cannot be created
    """
    permission_and_email_status = create_portfolio_permission_or_invitation(
        email=email,
        portfolio=portfolio,
        requestor=requestor,
        roles=roles,
        additional_permissions=additional_permissions,
        send_email=True,
    )
    return permission_and_email_status[0]


def create_portfolio_permission_or_invitation(
    email: str,
    portfolio: Portfolio,
    requestor: User,
    roles: list,
    additional_permissions: list = None,
    send_email: bool = True,
    permission: UserPortfolioPermission = None,
):
    """
    Create a UserPortfolioPermission for an existing user or an invitation with a new email.

    Returns the saved permission and whether emails were sent.
    """
    email = _get_portfolio_permission_email(email, permission)
    requested_user = _get_portfolio_permission_user(email, permission)

    try:
        validate_portfolio_permission_or_invitation(
            email=email,
            portfolio=portfolio,
        )
    except ValidationError as error:
        raise InvitationError(error.messages[0]) from error

    try:
        with transaction.atomic():
            permission = _save_portfolio_permission(
                permission=permission,
                email=email,
                portfolio=portfolio,
                user=requested_user,
                roles=roles,
                additional_permissions=additional_permissions,
            )
            # Temporary support for legacy invitations
            _save_legacy_portfolio_invitation(
                email=email,
                portfolio=portfolio,
                user=requested_user,
                roles=roles,
                additional_permissions=additional_permissions,
            )
            send_invitation_email = _must_send_portfolio_permission_email(requested_user, send_email)
            email_sent = True
            if send_invitation_email:
                email_sent = _send_portfolio_permission_email(
                    email=email,
                    requestor=requestor,
                    portfolio=portfolio,
                    roles=roles,
                )
                _set_portfolio_invitation_details(permission, requestor)

            logger.info(f"Created portfolio permission or invitation for {email} to portfolio {portfolio.id}")
            return permission, email_sent

    except Exception as e:
        logger.error(
            f"Failed to create portfolio permission or invitation for {email}: {e}",
            exc_info=True,
        )
        raise


def _get_portfolio_permission_email(email, permission):
    requested_email = None

    # Once an invitation is accepted, always prefer the user record.
    if permission:
        if permission.user:
            if permission.user.email:
                requested_email = permission.user.email

    if not requested_email:
        if email:
            requested_email = email

    if not requested_email:
        if permission:
            if permission.email:
                requested_email = permission.email

    if not requested_email:
        raise InvitationError("An email address is required.")

    return requested_email.lower()


def _get_portfolio_permission_user(email, permission):
    # If the email belongs to a current user, the permission should point at that user.
    requested_user = get_requested_user(email)
    if requested_user:
        return requested_user

    if permission:
        if permission.user:
            return permission.user

    return None


def validate_portfolio_permission_or_invitation(email, portfolio):
    if check_duplicate_portfolio_invitation(email, portfolio):
        raise ValidationError(f"{email} has an existing invitation or is already a member of this portfolio.")


def _save_portfolio_permission(
    permission,
    email,
    portfolio,
    user,
    roles,
    additional_permissions,
):
    if permission is None:
        permission = UserPortfolioPermission()

    permission.email = email
    permission.portfolio = portfolio
    permission.user = user
    permission.roles = roles
    permission.additional_permissions = additional_permissions
    permission.status = get_portfolio_permission_status(user)
    permission.save()

    return permission


def _save_legacy_portfolio_invitation(
    email,
    portfolio,
    user,
    roles,
    additional_permissions,
):

    legacy_invitation = PortfolioInvitation(
        email=email,
        portfolio=portfolio,
        roles=roles,
        additional_permissions=additional_permissions,
    )
    legacy_invitation.save()

    if user:
        legacy_invitation.retrieve()
        legacy_invitation.save()

    return legacy_invitation


def get_portfolio_permission_status(user):
    if user is None:
        return UserPortfolioPermission.Status.INVITED

    return UserPortfolioPermission.Status.ACCEPTED


def _set_portfolio_invitation_details(permission, requestor):
    # invited_by and invited_at mean the invitation email path completed without
    # raising an exception.
    permission.invited_by = requestor
    permission.invited_at = timezone.now()
    permission.save(update_fields=["invited_by", "invited_at"])


def _send_portfolio_permission_email(email, requestor, portfolio, roles):
    return send_portfolio_invitation_email(
        email=email,
        requestor=requestor,
        portfolio=portfolio,
        is_admin_invitation=_is_portfolio_admin_invitation(roles),
    )


def _must_send_portfolio_permission_email(user, send_email):
    if user is None:
        return True

    if send_email:
        return True

    return False


def _is_portfolio_admin_invitation(roles):
    if not roles:
        return False

    if UserPortfolioRoleChoices.ORGANIZATION_ADMIN in roles:
        return True

    return False


def _check_existing_domain_invitation(email: str, domain: Domain, requested_user):
    """
    Check for existing domain invitations or roles.

    Raises:
        AlreadyDomainManagerError: If user is already a domain manager
        AlreadyDomainInvitedError: If user has already been invited
    """
    # Check for duplicates in new model
    if requested_user:
        existing_role = UserDomainRole.objects.filter(user=requested_user, domain=domain).exists()
        if existing_role:
            raise AlreadyDomainManagerError(email)

    invited = UserDomainRole.objects.filter(email=email, domain=domain, status=UserDomainRole.Status.INVITED).exists()
    if invited:
        raise AlreadyDomainInvitedError(email)

    # Check for duplicates in legacy model
    try:
        invite = DomainInvitation.objects.get(email=email, domain=domain)
        if invite.status == DomainInvitation.DomainInvitationStatus.RETRIEVED:
            raise AlreadyDomainManagerError(email)
        elif invite.status == DomainInvitation.DomainInvitationStatus.INVITED:
            raise AlreadyDomainInvitedError(email)
    except DomainInvitation.DoesNotExist:
        pass


def invite_to_domain(
    email: str,
    domain: Domain,
    requestor: User,
    role: str,
    is_member_of_different_org: bool = False,
):
    """
    Invite a user to a domain.
    Creates invitation in new model (UserDomainRole).

    Args:
        email: Email address of the invitee
        domain: Domain to invite user to
        requestor: User creating the invitation
        role: Domain role to assign
        is_member_of_different_org: Whether user belongs to different org

    Returns:
        UserDomainRole object

    Raises:
        AlreadyDomainManagerError: If user is already a domain manager
        AlreadyDomainInvitedError: If user has already been invited
    """
    email = email.lower()
    requested_user = get_requested_user(email)

    _check_existing_domain_invitation(email, domain, requested_user)

    try:
        with transaction.atomic():
            if requested_user:
                # User exists - create UserDomainRole directly
                domain_role = UserDomainRole.objects.create(
                    user=requested_user,
                    domain=domain,
                    role=role,
                    status=UserDomainRole.Status.INVITED,
                    email=email,
                    invited_by=requestor,
                    invited_at=timezone.now(),
                )
            else:
                # User doesn't exist - create invitation in UserDomainRole
                domain_role = UserDomainRole.objects.create(
                    user=None,
                    domain=domain,
                    role=role,
                    status=UserDomainRole.Status.INVITED,
                    email=email,
                    invited_by=requestor,
                    invited_at=timezone.now(),
                )

            # Send invitation email
            send_domain_invitation_email(
                email=email,
                requestor=requestor,
                domains=domain,
                is_member_of_different_org=is_member_of_different_org,
                requested_user=requested_user,
            )

            logger.info(f"Created domain invitation for {email} " f"to domain {domain.id}")
            return domain_role

    except Exception as e:
        logger.error(
            f"Failed to create domain invitation for {email}: {e}",
            exc_info=True,
        )
        raise


def invite_to_domains_bulk(
    email: str,
    domains,
    requestor: User,
    role: str,
    is_member_of_different_org: bool = False,
):
    """
    Invite a user to multiple domains at once.
    Creates invitations in new model (UserDomainRole).
    Used when adding domains to an invited portfolio member.

    Args:
        email: Email address of the invitee
        domains: QuerySet or list of Domain objects
        requestor: User creating the invitations
        role: Domain role to assign
        is_member_of_different_org: Whether user belongs to different org

    Returns:
        List of UserDomainRole objects

    Raises:
        InvitationError: If invitations cannot be created
    """
    email = email.lower()
    requested_user = get_requested_user(email)

    # Convert to list if needed for multiple iterations
    domain_list = list(domains)

    if not domain_list:
        return []

    try:
        with transaction.atomic():
            domain_roles = []

            # Fetch existing roles in bulk to avoid N+1 queries
            domain_ids = [d.id for d in domain_list]
            existing_roles = {
                role.domain_id: role for role in UserDomainRole.objects.filter(email=email, domain_id__in=domain_ids)
            }

            for domain in domain_list:
                existing_role = existing_roles.get(domain.id)

                if existing_role:
                    # Update status if rejected
                    if existing_role.status == UserDomainRole.Status.REJECTED:
                        existing_role.status = UserDomainRole.Status.INVITED
                        existing_role.save()
                    domain_roles.append(existing_role)
                else:
                    # Create new role invitation
                    if requested_user:
                        domain_role = UserDomainRole.objects.create(
                            user=requested_user,
                            domain=domain,
                            role=role,
                            status=UserDomainRole.Status.INVITED,
                            email=email,
                            invited_by=requestor,
                            invited_at=timezone.now(),
                        )
                    else:
                        domain_role = UserDomainRole.objects.create(
                            user=None,
                            domain=domain,
                            role=role,
                            status=UserDomainRole.Status.INVITED,
                            email=email,
                            invited_by=requestor,
                            invited_at=timezone.now(),
                        )
                    domain_roles.append(domain_role)

            # Send single email for all domains
            send_domain_invitation_email(
                email=email,
                requestor=requestor,
                domains=domain_list,
                is_member_of_different_org=is_member_of_different_org,
                requested_user=requested_user,
            )

            logger.info(f"Created bulk domain invitations for {email} " f"to {len(domain_list)} domains")
            return domain_roles

    except Exception as e:
        logger.error(
            f"Failed to create bulk domain invitations for {email}: {e}",
            exc_info=True,
        )
        raise


def get_pending_invitations(user: User):
    """
    Retrieve all pending invitations for a user by email.
    Checks both legacy and new invitation models.

    Args:
        user: User to check invitations for

    Returns:
        dict with 'portfolio_invitations' and 'domain_invitations' lists
    """
    email = user.email.lower() if user.email else None
    if not email:
        return {"portfolio_invitations": [], "domain_invitations": []}

    # Get new model invitations with related objects
    portfolio_permissions = UserPortfolioPermission.objects.filter(
        email=email, status=UserPortfolioPermission.Status.INVITED
    ).select_related("portfolio", "invited_by")

    domain_roles = UserDomainRole.objects.filter(email=email, status=UserDomainRole.Status.INVITED).select_related(
        "domain", "invited_by"
    )

    # Get legacy model invitations with related objects
    legacy_portfolio_invitations = PortfolioInvitation.objects.filter(
        email=email,
        status=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
    ).select_related("portfolio")

    legacy_domain_invitations = DomainInvitation.objects.filter(
        email=email, status=DomainInvitation.DomainInvitationStatus.INVITED
    ).select_related("domain")

    return {
        "portfolio_permissions": list(portfolio_permissions),
        "domain_roles": list(domain_roles),
        "legacy_portfolio_invitations": list(legacy_portfolio_invitations),
        "legacy_domain_invitations": list(legacy_domain_invitations),
    }


def accept_portfolio_invitation(user: User, portfolio: Portfolio):
    """
    Accept a portfolio invitation for a user.
    Updates both legacy and new models.

    Args:
        user: User accepting the invitation
        portfolio: Portfolio being accepted

    Returns:
        UserPortfolioPermission object or None
    """
    email = user.email.lower() if user.email else None
    if not email:
        return None

    try:
        with transaction.atomic():
            # Accept new model invitation
            permission = UserPortfolioPermission.objects.filter(
                email=email,
                portfolio=portfolio,
                status=UserPortfolioPermission.Status.INVITED,
            ).first()

            if permission:
                permission.user = user
                permission.status = UserPortfolioPermission.Status.ACCEPTED
                permission.accepted_at = timezone.now()
                permission.save()

            # Accept legacy model invitation
            legacy_invitation = PortfolioInvitation.objects.filter(
                email=email,
                portfolio=portfolio,
                status=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
            ).first()

            if legacy_invitation:
                legacy_invitation.retrieve()
                legacy_invitation.save()

            logger.info(f"User {user.id} accepted portfolio invitation " f"for {portfolio.id}")
            return permission

    except Exception as e:
        logger.error(
            f"Failed to accept portfolio invitation for user {user.id}: {e}",
            exc_info=True,
        )
        raise


def accept_domain_invitation(user: User, domain: Domain):
    """
    Accept a domain invitation for a user. Updates both legacy and new models.

    Args:
        user: User accepting the invitation
        domain: Domain being accepted

    Returns:
        UserDomainRole object or None
    """
    email = user.email.lower() if user.email else None
    if not email:
        return None

    try:
        with transaction.atomic():
            # Accept new model invitation
            domain_role = UserDomainRole.objects.filter(
                email=email,
                domain=domain,
                status=UserDomainRole.Status.INVITED,
            ).first()

            if domain_role:
                domain_role.user = user
                domain_role.status = UserDomainRole.Status.ACCEPTED
                domain_role.accepted_at = timezone.now()
                domain_role.save()

            # Accept legacy model invitation
            legacy_invitation = DomainInvitation.objects.filter(
                email=email,
                domain=domain,
                status=DomainInvitation.DomainInvitationStatus.INVITED,
            ).first()

            if legacy_invitation:
                legacy_invitation.retrieve()
                legacy_invitation.save()

            logger.info(f"User {user.id} accepted domain invitation for {domain.id}")
            return domain_role

    except Exception as e:
        logger.error(
            f"Failed to accept domain invitation for user {user.id}: {e}",
            exc_info=True,
        )
        raise


def cancel_domain_invitation(email: str, domain: Domain):
    """
    Cancel a pending domain invitation.
    Updates both legacy and new models.

    Args:
        email: Email address of the invitee
        domain: Domain to cancel invitation for

    Returns:
        True if invitation was canceled, False if not found
    """
    email = email.lower()

    try:
        with transaction.atomic():
            canceled = False

            # Cancel new model invitation
            domain_role = UserDomainRole.objects.filter(
                email=email,
                domain=domain,
                status=UserDomainRole.Status.INVITED,
            ).first()

            if domain_role:
                domain_role.status = UserDomainRole.Status.REJECTED
                domain_role.save()
                canceled = True

            # Cancel legacy model invitation
            legacy_invitation = DomainInvitation.objects.filter(
                email=email,
                domain=domain,
                status=DomainInvitation.DomainInvitationStatus.INVITED,
            ).first()

            if legacy_invitation:
                legacy_invitation.status = DomainInvitation.DomainInvitationStatus.CANCELED
                legacy_invitation.save()
                canceled = True

            if canceled:
                logger.info(f"Canceled domain invitation for {email} " f"to domain {domain.id}")

            return canceled

    except Exception as e:
        logger.error(
            f"Failed to cancel domain invitation for {email}: {e}",
            exc_info=True,
        )
        raise


def cancel_portfolio_invitation(email: str, portfolio: Portfolio):
    """
    Cancel a pending portfolio invitation.
    Updates both legacy and new models.

    Args:
        email: Email address of the invitee
        portfolio: Portfolio to cancel invitation for

    Returns:
        True if invitation was canceled, False if not found
    """
    email = email.lower()

    try:
        with transaction.atomic():
            canceled = False

            # Cancel new model invitation
            permission = UserPortfolioPermission.objects.filter(
                email=email,
                portfolio=portfolio,
                status=UserPortfolioPermission.Status.INVITED,
            ).first()

            if permission:
                permission.status = UserPortfolioPermission.Status.REJECTED
                permission.save()
                canceled = True

            # Cancel legacy model invitation
            legacy_invitation = PortfolioInvitation.objects.filter(
                email=email,
                portfolio=portfolio,
                status=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
            ).first()

            if legacy_invitation:
                # Note: PortfolioInvitation doesn't have CANCELED status
                # so we delete the invitation instead
                legacy_invitation.delete()
                canceled = True

            if canceled:
                logger.info(f"Canceled portfolio invitation for {email} " f"to portfolio {portfolio.id}")

            return canceled

    except Exception as e:
        logger.error(
            f"Failed to cancel portfolio invitation for {email}: {e}",
            exc_info=True,
        )
        raise


def reactivate_domain_invitation(email: str, domain: Domain):
    """
    Reactivate a previously canceled/rejected domain invitation.
    Updates both legacy and new models.

    Args:
        email: Email address of the invitee
        domain: Domain to reactivate invitation for

    Returns:
        True if invitation was reactivated, False if not found
    """
    email = email.lower()

    try:
        with transaction.atomic():
            reactivated = False

            # Reactivate new model invitation
            domain_role = UserDomainRole.objects.filter(
                email=email,
                domain=domain,
                status=UserDomainRole.Status.REJECTED,
            ).first()

            if domain_role:
                domain_role.status = UserDomainRole.Status.INVITED
                domain_role.save()
                reactivated = True

            # Reactivate legacy model invitation
            legacy_invitation = DomainInvitation.objects.filter(
                email=email,
                domain=domain,
                status=DomainInvitation.DomainInvitationStatus.CANCELED,
            ).first()

            if legacy_invitation:
                legacy_invitation.status = DomainInvitation.DomainInvitationStatus.INVITED
                legacy_invitation.save()
                reactivated = True

            if reactivated:
                logger.info(f"Reactivated domain invitation for {email} " f"to domain {domain.id}")

            return reactivated

    except Exception as e:
        logger.error(
            f"Failed to reactivate domain invitation for {email}: {e}",
            exc_info=True,
        )
        raise


def check_duplicate_domain_invitation(email: str, domain: Domain):
    """Check for duplicate domain invitation in both models."""
    email = email.lower()

    # Check new model
    if UserDomainRole.objects.filter(email=email, domain=domain).exists():
        return True

    # Check legacy model for active invitations
    if (
        DomainInvitation.objects.filter(email=email, domain=domain)
        .exclude(
            status__in=[
                DomainInvitation.DomainInvitationStatus.RETRIEVED,
                DomainInvitation.DomainInvitationStatus.CANCELED,
            ]
        )
        .exists()
    ):
        return True

    return False


def check_duplicate_portfolio_invitation(email: str, portfolio: Portfolio):
    """Check for duplicate portfolio invitation in both models."""
    email = email.lower()

    # Check new model
    if UserPortfolioPermission.objects.filter(email__iexact=email, portfolio=portfolio).exists():
        return True

    if UserPortfolioPermission.objects.filter(user__email__iexact=email, portfolio=portfolio).exists():
        return True

    # Check legacy model for active invitations
    if (
        PortfolioInvitation.objects.filter(email=email, portfolio=portfolio)
        .exclude(status=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)
        .exists()
    ):
        return True

    return False
