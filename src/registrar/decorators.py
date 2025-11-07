import logging
import functools
from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from registrar.models import Domain, DomainInformation, DomainInvitation, DomainRequest, UserDomainRole
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from functools import wraps
from registrar.utility.db_timeouts import pg_timeouts


logger = logging.getLogger(__name__)

# Constants for clarity
ALL = "all"
IS_STAFF = "is_staff"
IS_CISA_ANALYST = "is_cisa_analyst"
IS_OMB_ANALYST = "is_omb_analyst"
IS_FULL_ACCESS = "is_full_access"
IS_DOMAIN_MANAGER = "is_domain_manager"
IS_DOMAIN_REQUEST_REQUESTER = "is_domain_request_requester"
IS_STAFF_MANAGING_DOMAIN = "is_staff_managing_domain"
HAS_DOMAIN_REQUESTS_VIEW_ALL = "has_domain_requests_view_all"
IS_PORTFOLIO_MEMBER = "is_portfolio_member"
IS_MULTIPLE_PORTFOLIOS_MEMBER = "is_multiple_portfolios_member"
IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER = "is_portfolio_member_and_domain_manager"
IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER = "is_domain_manager_and_not_portfolio_member"
HAS_PORTFOLIO_DOMAINS_ANY_PERM = "has_portfolio_domains_any_perm"
HAS_PORTFOLIO_DOMAINS_VIEW_ALL = "has_portfolio_domains_view_all"
HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM = "has_portfolio_domain_requests_any_perm"
HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT = "has_portfolio_domain_requests_edit"
HAS_PORTFOLIO_MEMBERS_ANY_PERM = "has_portfolio_members_any_perm"
HAS_PORTFOLIO_MEMBERS_EDIT = "has_portfolio_members_edit"
HAS_PORTFOLIO_MEMBERS_VIEW = "has_portfolio_members_view"
HAS_LEGACY_AND_ORG_USER = "has_legacy_and_org_user"


def grant_access(*rules):
    """
    A decorator that enforces access control based on specified rules.

    Usage:
        - Multiple rules in a single decorator:
          @grant_access(IS_STAFF, IS_SUPERUSER, IS_DOMAIN_MANAGER)

        - Stacked decorators for separate rules:
          @grant_access(IS_SUPERUSER)
          @grant_access(IS_DOMAIN_MANAGER)

    The decorator supports both function-based views (FBVs) and class-based views (CBVs).
    """

    def decorator(view):
        if isinstance(view, type):  # Check if decorating a class-based view (CBV)
            original_dispatch = view.dispatch  # Store the original dispatch method

            @method_decorator(grant_access(*rules))  # Apply the decorator to dispatch
            def wrapped_dispatch(self, request, *args, **kwargs):
                if not _user_has_permission(request.user, request, rules, **kwargs):
                    raise PermissionDenied  # Deny access if the user lacks permission
                return original_dispatch(self, request, *args, **kwargs)

            view.dispatch = wrapped_dispatch  # Replace the dispatch method
            return view

        else:  # If decorating a function-based view (FBV)
            view.has_explicit_access = True  # Mark the view as having explicit access control
            existing_rules = getattr(view, "_access_rules", set())  # Retrieve existing rules
            existing_rules.update(rules)  # Merge with new rules
            view._access_rules = existing_rules  # Store updated rules

            @functools.wraps(view)
            def wrapper(request, *args, **kwargs):
                if not _user_has_permission(request.user, request, rules, **kwargs):
                    raise PermissionDenied  # Deny access if the user lacks permission
                return view(request, *args, **kwargs)  # Proceed with the original view

            return wrapper

    return decorator


def _user_has_permission(user, request, rules, **kwargs):
    """
    Determines if the user meets the required permission rules.

    This function evaluates a set of predefined permission rules to check whether a user has access
    to a specific view. It supports various access control conditions, including staff status,
    domain management roles, and portfolio-related permissions.

    Parameters:
        - user: The user requesting access.
        - request: The HTTP request object.
        - rules: A set of access control rules to evaluate.
        - **kwargs: Additional keyword arguments used in specific permission checks.

    Returns:
        - True if the user satisfies any of the specified rules.
        - False otherwise.
    """

    # Skip authentication if @login_not_required is applied
    if getattr(request, "login_not_required", False):
        return True

    # Allow everyone if `ALL` is in rules
    if ALL in rules:
        return True

    # Ensure user is authenticated and not restricted
    if not user.is_authenticated or user.is_restricted():
        return False

    portfolio = _resolve_portfolio(request, **kwargs)
    session_portfolio = request.session.get("portfolio")
    is_org = bool(portfolio and user.is_org_user_for_portfolio(portfolio))

    # Define permission checks
    permission_checks = [
        (IS_STAFF, lambda: user.is_staff),
        (IS_CISA_ANALYST, lambda: user.has_perm("registrar.analyst_access_permission")),
        (IS_OMB_ANALYST, lambda: user.groups.filter(name="omb_analysts_group").exists()),
        (IS_FULL_ACCESS, lambda: user.has_perm("registrar.full_access_permission")),
        (
            IS_DOMAIN_MANAGER,
            lambda: (
                _is_domain_manager(user, **kwargs)
                and (
                    # Legacy / not in org context, domain manager is fine
                    not session_portfolio
                    # In Org mode, domain must belong to the active session portfolio
                    or _domain_exists_under_portfolio(session_portfolio, kwargs.get("domain_pk"))
                )
            ),
        ),
        (IS_STAFF_MANAGING_DOMAIN, lambda: _is_staff_managing_domain(request, **kwargs)),
        (IS_PORTFOLIO_MEMBER, lambda: is_org),
        (IS_MULTIPLE_PORTFOLIOS_MEMBER, lambda: user.is_multiple_orgs_user(request)),
        (
            HAS_PORTFOLIO_DOMAINS_VIEW_ALL,
            lambda: is_org
            and user.has_view_all_domains_portfolio_permission(portfolio)
            and _domain_exists_under_portfolio(portfolio, kwargs.get("domain_pk")),
        ),
        (
            HAS_PORTFOLIO_DOMAINS_ANY_PERM,
            lambda: is_org
            and user.has_any_domains_portfolio_permission(portfolio)
            and _domain_exists_under_portfolio(portfolio, kwargs.get("domain_pk")),
        ),
        (
            IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER,
            lambda: _is_domain_manager(user, **kwargs)
            and is_org
            and _domain_exists_under_portfolio(portfolio, kwargs.get("domain_pk")),
        ),
        (
            IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER,
            lambda: _is_domain_manager(user, **kwargs) and not is_org and not portfolio,
        ),
        (
            IS_DOMAIN_REQUEST_REQUESTER,
            lambda: (
                _is_domain_request_requester(user, kwargs.get("domain_request_pk")) and not user.is_any_org_user()
            ),
        ),
        (
            HAS_DOMAIN_REQUESTS_VIEW_ALL,
            lambda: _can_view_all_domain_requests(user, request, kwargs.get("domain_request_pk"), portfolio),
        ),
        (
            HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM,
            lambda: is_org
            and user.has_any_requests_portfolio_permission(portfolio)
            and _domain_request_exists_under_portfolio(portfolio, kwargs.get("domain_request_pk")),
        ),
        (
            HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT,
            lambda: _has_portfolio_domain_requests_edit(user, portfolio, kwargs.get("domain_request_pk"))
            and _domain_request_exists_under_portfolio(portfolio, kwargs.get("domain_request_pk")),
        ),
        (
            HAS_PORTFOLIO_MEMBERS_ANY_PERM,
            lambda: is_org
            and (
                user.has_view_members_portfolio_permission(portfolio)
                or user.has_edit_members_portfolio_permission(portfolio)
            )
            and _member_checks(portfolio, kwargs),
        ),
        (
            HAS_PORTFOLIO_MEMBERS_EDIT,
            lambda: is_org
            and (
                user.has_view_members_portfolio_permission(portfolio)
                or user.has_edit_members_portfolio_permission(portfolio)
            )
            and _member_checks(portfolio, kwargs),
        ),
        (
            HAS_PORTFOLIO_MEMBERS_VIEW,
            lambda: is_org
            and user.has_view_members_portfolio_permission(portfolio)
            and _member_checks(portfolio, kwargs),
        ),
        (HAS_LEGACY_AND_ORG_USER, lambda: user.has_legacy_domain() and user.is_any_org_user()),
    ]
    # Check conditions iteratively
    return any(check() for rule, check in permission_checks if rule in rules)


def _has_portfolio_domain_requests_edit(user, portfolio, domain_request_id):
    if domain_request_id and not _is_domain_request_requester(user, domain_request_id):
        return False
    return bool(portfolio) and user.has_edit_request_portfolio_permission(portfolio)


def _is_domain_manager(user, **kwargs):
    """
    Determines if the given user is a domain manager for a specified domain.

    - First, it checks if 'domain_pk' is present in the URL parameters.
    - If 'domain_pk' exists, it verifies if the user has a domain role for that domain.
    - If 'domain_pk' is absent, it checks for 'domain_invitation_pk' to determine if the user
      has domain permissions through an invitation.

    Returns:
        bool: True if the user is a domain manager, False otherwise.
    """
    domain_id = kwargs.get("domain_pk")
    if domain_id:
        return UserDomainRole.objects.filter(user=user, domain_id=domain_id).exists()
    domain_invitation_id = kwargs.get("domain_invitation_pk")
    if domain_invitation_id:
        return DomainInvitation.objects.filter(id=domain_invitation_id, domain__permissions__user=user).exists()
    return False


def _p_id(portfolio_or_id):
    if hasattr(portfolio_or_id, "pk"):
        return portfolio_or_id.pk
    return portfolio_or_id


def _domain_exists_under_portfolio(portfolio, domain_pk):
    """Checks to see if the given domain exists under the provided portfolio.
    HELPFUL REMINDER: Watch for typos! Verify that the kwarg key exists before using this function.
    Returns True if the pk is falsy. Otherwise, returns a bool if said object exists.
    """
    # The view expects this, and the page will throw an error without this if it needs it.
    # Thus, if it is none, we are not checking on a specific record and therefore there is nothing to check.
    if not domain_pk:
        logger.warning(
            "_domain_exists_under_portfolio => Could not find domain_pk. "
            "This is a non-issue if called from the right context."
        )
        return True
    return Domain.objects.filter(domain_info__portfolio=portfolio, id=domain_pk).exists()


def _domain_request_exists_under_portfolio(portfolio, domain_request_pk):
    """Checks to see if the given domain request exists under the provided portfolio.
    HELPFUL REMINDER: Watch for typos! Verify that the kwarg key exists before using this function.
    Returns True if the pk is falsy. Otherwise, returns a bool if said object exists.
    """
    # The view expects this, and the page will throw an error without this if it needs it.
    # Thus, if it is none, we are not checking on a specific record and therefore there is nothing to check.
    if not domain_request_pk:
        logger.warning(
            "_domain_request_exists_under_portfolio => Could not find domain_request_pk. "
            "This is a non-issue if called from the right context."
        )
        return True
    return DomainRequest.objects.filter(portfolio=portfolio, id=domain_request_pk).exists()


def _member_exists_under_portfolio(portfolio, member_pk):
    """Checks to see if the given UserPortfolioPermission exists under the provided portfolio.
    HELPFUL REMINDER: Watch for typos! Verify that the kwarg key exists before using this function.
    Returns True if the pk is falsy. Otherwise, returns a bool if said object exists.
    """
    # The view expects this, and the page will throw an error without this if it needs it.
    # Thus, if it is none, we are not checking on a specific record and therefore there is nothing to check.
    if not member_pk:
        logger.warning(
            "_member_exists_under_portfolio => Could not find member_pk. "
            "This is a non-issue if called from the right context."
        )
        return True
    return UserPortfolioPermission.objects.filter(portfolio=portfolio, id=member_pk).exists()


def _member_invitation_exists_under_portfolio(portfolio, invitedmember_pk):
    """Checks to see if the given PortfolioInvitation exists under the provided portfolio.
    HELPFUL REMINDER: Watch for typos! Verify that the kwarg key exists before using this function.
    Returns True if the pk is falsy. Otherwise, returns a bool if said object exists.
    """
    # The view expects this, and the page will throw an error without this if it needs it.
    # Thus, if it is none, we are not checking on a specific record and therefore there is nothing to check.
    if not invitedmember_pk:
        logger.warning(
            "_member_invitation_exists_under_portfolio => Could not find invitedmember_pk. "
            "This is a non-issue if called from the right context."
        )
        return True
    return PortfolioInvitation.objects.filter(portfolio=portfolio, id=invitedmember_pk).exists()


def _is_domain_request_requester(user, domain_request_pk):
    """Checks to see if the user is the requester of a domain request
    with domain_request_pk."""
    if domain_request_pk:
        return DomainRequest.objects.filter(requester=user, id=domain_request_pk).exists()
    return True


def _is_portfolio_member(request):
    """Checks to see if the user in the request is a member of the
    portfolio in the request's session."""
    return request.user.is_org_user(request)


def _is_staff_managing_domain(request, **kwargs):
    """
    Determines whether a staff user (analyst or superuser) has permission to manage a domain
    that they did not create or were not invited to.

    The function enforces:
    1. **User Authorization** - The user must have `analyst_access_permission` or `full_access_permission`.
    2. **Valid Session Context** - The user must have explicitly selected the domain for management
       via an 'analyst action' (e.g., by clicking 'Manage Domain' in the admin interface).
    3. **Domain Status Check** - Only domains in specific statuses (e.g., APPROVED, IN_REVIEW, etc.)
       can be managed, except in cases where the domain lacks a status due to errors.

    Process:
    - First, the function retrieves the `domain_pk` from the URL parameters.
    - If `domain_pk` is not provided, it attempts to resolve the domain via `domain_invitation_pk`.
    - It checks if the user has the required permissions.
    - It verifies that the user has an active 'analyst action' session for the domain.
    - Finally, it ensures that the domain is in a status that allows management.

    Returns:
        bool: True if the user is allowed to manage the domain, False otherwise.
    """

    domain_id = kwargs.get("domain_pk")
    if not domain_id:
        domain_invitation_id = kwargs.get("domain_invitation_pk")
        domain_invitation = DomainInvitation.objects.filter(id=domain_invitation_id).first()
        if domain_invitation:
            domain_id = domain_invitation.domain_id

    # Check if the request user is permissioned...
    user_is_analyst_or_superuser = request.user.has_perm(
        "registrar.analyst_access_permission"
    ) or request.user.has_perm("registrar.full_access_permission")

    if not user_is_analyst_or_superuser:
        return False

    # Check if the user is attempting a valid edit action.
    # In other words, if the analyst/admin did not click
    # the 'Manage Domain' button in /admin,
    # then they cannot access this page.
    session = request.session
    can_do_action = (
        "analyst_action" in session
        and "analyst_action_location" in session
        and session["analyst_action_location"] == domain_id
    )

    if not can_do_action:
        return False

    # Analysts may manage domains, when they are in these statuses:
    valid_domain_statuses = [
        DomainRequest.DomainRequestStatus.APPROVED,
        DomainRequest.DomainRequestStatus.IN_REVIEW,
        DomainRequest.DomainRequestStatus.REJECTED,
        DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        # Edge case - some domains do not have
        # a status or DomainInformation... aka a status of 'None'.
        # It is necessary to access those to correct errors.
        None,
    ]

    requested_domain = DomainInformation.objects.filter(domain_id=domain_id).first()

    # if no domain information or domain request exist, the user
    # should be able to manage the domain; however, if domain information
    # and domain request exist, and domain request is not in valid status,
    # user should not be able to manage domain
    if (
        requested_domain
        and requested_domain.domain_request
        and requested_domain.domain_request.status not in valid_domain_statuses
    ):
        return False

    # Valid session keys exist,
    # the user is permissioned,
    # and it is in a valid status
    return True


def _can_view_all_domain_requests(user, request, domain_request_pk, portfolio=None):
    """
    Determines if the user has view-all permission for domain requests.
    This permission allows users to view domain request details without editing.
    Handles both portfolio and non-portfolio domain requests.
    """
    if not domain_request_pk:
        return False

    if portfolio:
        has_perm = user.has_view_all_domain_requests_portfolio_permission(portfolio)
        exists = _domain_request_exists_under_portfolio(portfolio, domain_request_pk)
        return has_perm and exists

    try:
        domain_request = DomainRequest.objects.get(pk=domain_request_pk)
    except DomainRequest.DoesNotExist:
        return False
    return _has_legacy_domain_request_view_access(user, domain_request)


def _has_legacy_domain_request_view_access(user, domain_request):
    """
    All of the ways a user can view a non-portfolio aka only applies to legacy mode domain request:
    Has the analyst_access_permission or
    Is the requester of the request or
    Has the full_access_permission
    """
    if user.has_perm("registrar.analyst_access_permission"):
        return True

    if domain_request.requester == user:
        return True

    if user.has_perm("registrar.full_access_permission"):
        return True

    return False


def allow_slow_queries(*, statement_ms=60000, lock_ms=60000, idle_tx_ms=None):
    def deco(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            with pg_timeouts(statement_ms=statement_ms, lock_ms=lock_ms, idle_tx_ms=idle_tx_ms):
                return view_func(*args, **kwargs)

        return wrapper

    return deco


def _member_checks(portfolio, kwargs):
    return (kwargs.get("member_pk") is None or _member_exists_under_portfolio(portfolio, kwargs.get("member_pk"))) and (
        kwargs.get("invitedmember_pk") is None
        or _member_invitation_exists_under_portfolio(portfolio, kwargs.get("invitedmember_pk"))
    )


def _resolve_portfolio(request, **kwargs):
    """
    Always return a Portfolio object if we can resolve one, else None.
    Resolution order:
    explicit portfolio param (GET / POST)
    infer from route kwargs (member_pk / invitedmember_pk / domain_request_pk / domain_pk)
    session['portfolio']
    """
    Portfolio = apps.get_model("registrar", "Portfolio")

    pid = request.GET.get("portfolio") or request.POST.get("portfolio")
    if pid:
        try:
            return Portfolio.objects.filter(pk=int(pid)).first()
        except (TypeError, ValueError):
            return None

    UPP = apps.get_model("registrar", "UserPortfolioPermission")
    PI = apps.get_model("registrar", "PortfolioInvitation")
    DR = apps.get_model("registrar", "DomainRequest")
    DI = apps.get_model("registrar", "DomainInformation")

    member_pk = kwargs.get("member_pk")
    if member_pk:
        pid = UPP.objects.filter(pk=member_pk).values_list("portfolio_id", flat=True).first()
        return Portfolio.objects.filter(pk=pid).first() if pid else None

    invitedmember_pk = kwargs.get("invitedmember_pk")
    if invitedmember_pk:
        pid = PI.objects.filter(pk=invitedmember_pk).values_list("portfolio_id", flat=True).first()
        return Portfolio.objects.filter(pk=pid).first() if pid else None

    domain_request_pk = kwargs.get("domain_request_pk")
    if domain_request_pk:
        pid = DR.objects.filter(pk=domain_request_pk).values_list("portfolio_id", flat=True).first()
        return Portfolio.objects.filter(pk=pid).first() if pid else None

    domain_pk = kwargs.get("domain_pk")
    if domain_pk:
        pid = DI.objects.filter(domain_id=domain_pk).values_list("portfolio_id", flat=True).first()
        return Portfolio.objects.filter(pk=pid).first() if pid else None

    sess_obj = request.session.get("portfolio")
    return sess_obj if getattr(sess_obj, "pk", None) else None


def resolve_portfolio(request, **kwargs):
    """Public alias for _resolve_portfolio_id, for use in views/tests."""
    return _resolve_portfolio(request, **kwargs)
