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
    ORGANIZATION_MEMBER = "organization_member", "Member"

    @classmethod
    def get_user_portfolio_role_label(cls, user_portfolio_role):
        try:
            return cls(user_portfolio_role).label if user_portfolio_role else None
        except ValueError:
            logger.warning(f"Invalid portfolio role: {user_portfolio_role}")
            return f"Unknown ({user_portfolio_role})"


class UserPortfolioPermissionChoices(models.TextChoices):
    """ """

    VIEW_ALL_DOMAINS = "view_all_domains", "View all domains and domain reports"
    VIEW_MANAGED_DOMAINS = "view_managed_domains", "View managed domains"

    VIEW_MEMBERS = "view_members", "View members"
    EDIT_MEMBERS = "edit_members", "Create and edit members"

    VIEW_ALL_REQUESTS = "view_all_requests", "View all requests"
    EDIT_REQUESTS = "edit_requests", "Create and edit requests"

    VIEW_PORTFOLIO = "view_portfolio", "View organization"
    EDIT_PORTFOLIO = "edit_portfolio", "Edit organization"

    # Domain: field specific permissions
    VIEW_SUBORGANIZATION = "view_suborganization", "View suborganization"
    EDIT_SUBORGANIZATION = "edit_suborganization", "Edit suborganization"

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
    PortfolioInvitation = apps.get_model("registrar.PortfolioInvitation")
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")

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
        existing_permissions = UserPortfolioPermission.objects.exclude(id=user_portfolio_permission.id).filter(
            user=user_portfolio_permission.user
        )
        if existing_permissions.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
            )

        existing_invitations = PortfolioInvitation.objects.filter(email=user_portfolio_permission.user.email).exclude(
            Q(portfolio=user_portfolio_permission.portfolio)
            | Q(status=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)
        )
        if existing_invitations.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio invitation. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
            )


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
    PortfolioInvitation = apps.get_model("registrar.PortfolioInvitation")
    UserPortfolioPermission = apps.get_model("registrar.UserPortfolioPermission")
    User = get_user_model()

    has_portfolio = bool(portfolio_invitation.portfolio_id)
    portfolio_permissions = set(portfolio_invitation.get_portfolio_permissions())

    # == Validate required fields == #
    if not has_portfolio and portfolio_permissions:
        raise ValidationError("When portfolio roles or additional permissions are assigned, portfolio is required.")

    if has_portfolio and not portfolio_permissions:
        raise ValidationError("When portfolio is assigned, portfolio roles or additional permissions are required.")

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
    user = User.objects.filter(email=portfolio_invitation.email).first()
    # If user returns None, then we check for global assignment of multiple_portfolios.
    # Otherwise we just check on the user.
    if not flag_is_active_for_user(user, "multiple_portfolios"):
        existing_permissions = UserPortfolioPermission.objects.filter(user=user)

        existing_invitations = PortfolioInvitation.objects.filter(email=portfolio_invitation.email).exclude(
            Q(id=portfolio_invitation.id) | Q(status=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)
        )

        if existing_permissions.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
            )

        if existing_invitations.exists():
            raise ValidationError(
                "This user is already assigned to a portfolio invitation. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
            )
