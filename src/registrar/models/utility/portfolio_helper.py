from registrar.utility import StrEnum
from django.db import models
from django.db.models import Q
from django.apps import apps
from django.forms import ValidationError
from registrar.utility.waffle import flag_is_active_for_user
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)


class UserPortfolioRoleChoices(models.TextChoices):
    """
    Roles make it easier for admins to look at
    """

    ORGANIZATION_ADMIN = "organization_admin", "Admin"
    ORGANIZATION_MEMBER = "organization_member", "Basic"

    @classmethod
    def get_user_portfolio_role_label(cls, user_portfolio_role):
        try:
            return cls(user_portfolio_role).label if user_portfolio_role else None
        except ValueError:
            logger.warning(f"Invalid portfolio role: {user_portfolio_role}")
            return f"Unknown ({user_portfolio_role})"


class UserPortfolioPermissionChoices(models.TextChoices):
    """ """

    VIEW_ALL_DOMAINS = "view_all_domains", "Viewer"
    VIEW_MANAGED_DOMAINS = "view_managed_domains", "Viewer, limited (domains they manage)"

    VIEW_MEMBERS = "view_members", "Viewer"
    EDIT_MEMBERS = "edit_members", "Manager"

    VIEW_ALL_REQUESTS = "view_all_requests", "Viewer"
    EDIT_REQUESTS = "edit_requests", "Requester"

    VIEW_PORTFOLIO = "view_portfolio", "Viewer"
    EDIT_PORTFOLIO = "edit_portfolio", "Manager"

    @classmethod
    def get_user_portfolio_permission_label(cls, user_portfolio_permission):
        return cls(user_portfolio_permission).label if user_portfolio_permission else None

    @classmethod
    def to_dict(cls):
        return {key: value.value for key, value in cls.__members__.items()}


class DomainRequestPermissionDisplay(StrEnum):
    """Stores display values for domain request permission combinations.

    Overview of values:
    - VIEWER_REQUESTER: "Viewer Requester"
    - VIEWER: "Viewer"
    - NONE: "None"
    """

    VIEWER_REQUESTER = "Viewer Requester"
    VIEWER = "Viewer"
    NONE = "None"


class MemberPermissionDisplay(StrEnum):
    """Stores display values for member permission combinations.

    Overview of values:
    - MANAGER: "Manager"
    - VIEWER: "Viewer"
    - NONE: "None"
    """

    MANAGER = "Manager"
    VIEWER = "Viewer"
    NONE = "None"


def get_readable_roles(roles):
    readable_roles = []
    if roles:
        readable_roles = sorted([UserPortfolioRoleChoices.get_user_portfolio_role_label(role) for role in roles])
    return readable_roles


def get_role_display(roles):
    """
    Returns a user-friendly display name for a given list of user roles.

    - If the user has the ORGANIZATION_ADMIN role, return "Admin".
    - If the user has the ORGANIZATION_MEMBER role, return "Basic".
    - If the user has neither role, return "-".

    Args:
        roles (list): A list of role strings assigned to the user.

    Returns:
        str: The display name for the highest applicable role.
    """
    if UserPortfolioRoleChoices.ORGANIZATION_ADMIN in roles:
        return "Admin"
    elif UserPortfolioRoleChoices.ORGANIZATION_MEMBER in roles:
        return "Basic"
    else:
        return "-"


def get_domains_display(roles, permissions):
    """
    Determines the display name for a user's domain viewing permissions.

    - If the user has the VIEW_ALL_DOMAINS permission, return "Viewer".
    - Otherwise, return "Viewer, limited".

    Args:
        roles (list): A list of role strings assigned to the user.
        permissions (list): A list of additional permissions assigned to the user.

    Returns:
        str: A string representing the user's domain viewing access.
    """
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, permissions)
    if UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS in all_permissions:
        return "Viewer"
    else:
        return "Viewer, limited"


def get_domains_description_display(roles, permissions):
    """
    Determines the display description for a user's domain viewing permissions.

    Args:
        roles (list): A list of role strings assigned to the user.
        permissions (list): A list of additional permissions assigned to the user.

    Returns:
        str: A string representing the user's domain viewing access description.
    """
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, permissions)
    if UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS in all_permissions:
        return "Can view all domains for the organization"
    else:
        return "Can view only the domains they manage"


def get_domain_requests_display(roles, permissions):
    """
    Determines the display name for a user's domain request permissions.

    - If the user has the EDIT_REQUESTS permission, return "Requester".
    - If the user has the VIEW_ALL_REQUESTS permission, return "Viewer".
    - Otherwise, return "No access".

    Args:
        roles (list): A list of role strings assigned to the user.
        permissions (list): A list of additional permissions assigned to the user.

    Returns:
        str: A string representing the user's domain request access level.
    """
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, permissions)
    if UserPortfolioPermissionChoices.EDIT_REQUESTS in all_permissions:
        return "Requester"
    elif UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS in all_permissions:
        return "Viewer"
    else:
        return "No access"


def get_domain_requests_description_display(roles, permissions):
    """
    Determines the display description for a user's domain request permissions.

    Args:
        roles (list): A list of role strings assigned to the user.
        permissions (list): A list of additional permissions assigned to the user.

    Returns:
        str: A string representing the user's domain request access level description.
    """
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, permissions)
    if UserPortfolioPermissionChoices.EDIT_REQUESTS in all_permissions:
        return "Can view all domain requests for the organization and create requests"
    elif UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS in all_permissions:
        return "Can view all domain requests for the organization"
    else:
        return "Cannot view or create domain requests"


def get_members_display(roles, permissions):
    """
    Determines the display name for a user's member management permissions.

    - If the user has the EDIT_MEMBERS permission, return "Manager".
    - If the user has the VIEW_MEMBERS permission, return "Viewer".
    - Otherwise, return "No access".

    Args:
        roles (list): A list of role strings assigned to the user.
        permissions (list): A list of additional permissions assigned to the user.

    Returns:
        str: A string representing the user's member management access level.
    """
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, permissions)
    if UserPortfolioPermissionChoices.EDIT_MEMBERS in all_permissions:
        return "Manager"
    elif UserPortfolioPermissionChoices.VIEW_MEMBERS in all_permissions:
        return "Viewer"
    else:
        return "No access"


def get_members_description_display(roles, permissions):
    """
    Determines the display description for a user's member management permissions.

    Args:
        roles (list): A list of role strings assigned to the user.
        permissions (list): A list of additional permissions assigned to the user.

    Returns:
        str: A string representing the user's member management access level description.
    """
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    all_permissions = UserPortfolioPermission.get_portfolio_permissions(roles, permissions)
    if UserPortfolioPermissionChoices.EDIT_MEMBERS in all_permissions:
        return "Can view and manage all member permissions"
    elif UserPortfolioPermissionChoices.VIEW_MEMBERS in all_permissions:
        return "Can view all member permissions"
    else:
        return "Cannot view member permissions"


def validate_user_portfolio_permission(user_portfolio_permission):
    """
    Validates a UserPortfolioPermission instance. Located in portfolio_helper to avoid circular imports
    between PortfolioInvitation and UserPortfolioPermission models.

    Used in UserPortfolioPermission.clean() for model validation.

    Validates:
    1. A portfolio must be assigned if roles or additional permissions are specified, and vice versa.
    2. Assigned roles do not include any forbidden permissions.
    3. If the 'multiple_portfolios' flag is inactive for the user,
    they must not have existing portfolio permissions or invitations.

    Raises:
        ValidationError: If any of the validation rules are violated.
    """
    has_portfolio = bool(user_portfolio_permission.portfolio_id)
    portfolio_permissions = set(user_portfolio_permission._get_portfolio_permissions())

    # == Validate required fields == #
    if not has_portfolio and portfolio_permissions:
        raise ValidationError("When portfolio roles or additional permissions are assigned, portfolio is required.")

    if has_portfolio and not portfolio_permissions:
        raise ValidationError("When portfolio is assigned, portfolio roles or additional permissions are required.")

    # == Validate role permissions. Compares existing permissions to forbidden ones. == #
    roles = user_portfolio_permission.roles if user_portfolio_permission.roles is not None else []
    bad_perms = user_portfolio_permission.get_forbidden_permissions(
        roles, user_portfolio_permission.additional_permissions
    )
    if bad_perms:
        readable_perms = [
            UserPortfolioPermissionChoices.get_user_portfolio_permission_label(perm) for perm in bad_perms
        ]
        readable_roles = [UserPortfolioRoleChoices.get_user_portfolio_role_label(role) for role in roles]
        raise ValidationError(
            f"These permissions cannot be assigned to {', '.join(readable_roles)}: <{', '.join(readable_perms)}>"
        )

    # == Validate the multiple_porfolios flag. == #
    if not flag_is_active_for_user(user_portfolio_permission.user, "multiple_portfolios"):
        existing_permissions, existing_invitations = get_user_portfolio_permission_associations(
            user_portfolio_permission
        )
        if existing_permissions.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios.",
                code="has_existing_permissions",
            )

        if existing_invitations.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio invitation. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios.",
                code="has_existing_invitations",
            )


def get_user_portfolio_permission_associations(user_portfolio_permission):
    """
    Retrieves the associations for a user portfolio invitation.

    Returns:
      A tuple:
        (existing_permissions, existing_invitations)
      where:
        - existing_permissions: UserPortfolioPermission objects excluding the current permission.
        - existing_invitations: PortfolioInvitation objects for the user email excluding
        the current invitation and those with status RETRIEVED.
    """
    PortfolioInvitation = apps.get_model("registrar.PortfolioInvitation")
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    existing_permissions = UserPortfolioPermission.objects.exclude(id=user_portfolio_permission.id).filter(
        user=user_portfolio_permission.user
    )
    existing_invitations = PortfolioInvitation.objects.filter(
        email__iexact=user_portfolio_permission.user.email
    ).exclude(
        Q(portfolio=user_portfolio_permission.portfolio)
        | Q(status=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)
    )
    return (existing_permissions, existing_invitations)


def validate_portfolio_invitation(portfolio_invitation):
    """
    Validates a PortfolioInvitation instance. Located in portfolio_helper to avoid circular imports
    between PortfolioInvitation and UserPortfolioPermission models.

    Used in PortfolioInvitation.clean() for model validation.

    Validates:
    1. A portfolio must be assigned if roles or additional permissions are specified, and vice versa.
    2. Assigned roles do not include any forbidden permissions.
    3. If the 'multiple_portfolios' flag is inactive for the user,
    they must not have existing portfolio permissions or invitations.

    Raises:
        ValidationError: If any of the validation rules are violated.
    """
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    User = get_user_model()

    has_portfolio = bool(portfolio_invitation.portfolio_id)
    portfolio_permissions = set(portfolio_invitation.get_portfolio_permissions())

    # == Validate required fields == #
    if not has_portfolio and portfolio_permissions:
        raise ValidationError("When portfolio roles or additional permissions are assigned, portfolio is required.")

    if has_portfolio and not portfolio_permissions:
        logger.info("User didn't provide both a valid email address and a role for the member.")

    # == Validate role permissions. Compares existing permissions to forbidden ones. == #
    roles = portfolio_invitation.roles if portfolio_invitation.roles is not None else []
    bad_perms = UserPortfolioPermission.get_forbidden_permissions(roles, portfolio_invitation.additional_permissions)
    if bad_perms:
        readable_perms = [
            UserPortfolioPermissionChoices.get_user_portfolio_permission_label(perm) for perm in bad_perms
        ]
        readable_roles = [UserPortfolioRoleChoices.get_user_portfolio_role_label(role) for role in roles]
        raise ValidationError(
            f"These permissions cannot be assigned to {', '.join(readable_roles)}: <{', '.join(readable_perms)}>"
        )

    # == Validate the multiple_porfolios flag. == #
    user = User.objects.filter(email__iexact=portfolio_invitation.email).first()

    # If user returns None, then we check for global assignment of multiple_portfolios.
    # Otherwise we just check on the user.
    if not flag_is_active_for_user(user, "multiple_portfolios"):
        existing_permissions, existing_invitations = get_portfolio_invitation_associations(portfolio_invitation)
        if existing_permissions.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios.",
                code="has_existing_permissions",
            )

        if existing_invitations.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio invitation. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios.",
                code="has_existing_invitations",
            )


def get_portfolio_invitation_associations(portfolio_invitation):
    """
    Retrieves the associations for a portfolio invitation.

    Returns:
      A tuple:
        (existing_permissions, existing_invitations)
      where:
        - existing_permissions: UserPortfolioPermission objects matching the email.
        - existing_invitations: PortfolioInvitation objects for the email excluding
        the current invitation and those with status RETRIEVED.
    """
    PortfolioInvitation = apps.get_model("registrar.PortfolioInvitation")
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    existing_permissions = UserPortfolioPermission.objects.filter(user__email__iexact=portfolio_invitation.email)
    existing_invitations = PortfolioInvitation.objects.filter(email__iexact=portfolio_invitation.email).exclude(
        Q(id=portfolio_invitation.id) | Q(status=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)
    )
    return (existing_permissions, existing_invitations)


def cleanup_after_portfolio_member_deletion(portfolio, email, user=None):
    """
    Cleans up after removing a portfolio member or a portfolio invitation.

    Args:
    portfolio: portfolio
    user: passed when removing a portfolio member.
    email: passed when removing a portfolio invitation, or passed as user.email
    when removing a portfolio member.
    """

    DomainInvitation = apps.get_model("registrar.DomainInvitation")
    UserDomainRole = apps.get_model("registrar.UserDomainRole")

    # Fetch domain invitations matching the criteria
    invitations = DomainInvitation.objects.filter(
        email=email, domain__domain_info__portfolio=portfolio, status=DomainInvitation.DomainInvitationStatus.INVITED
    )

    # Call `cancel_invitation` on each invitation
    for invitation in invitations:
        invitation.cancel_invitation()
        invitation.save()

    if user:
        # Remove user's domain roles for the current portfolio
        UserDomainRole.objects.filter(user=user, domain__domain_info__portfolio=portfolio).delete()
