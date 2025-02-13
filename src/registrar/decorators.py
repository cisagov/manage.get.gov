import functools
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from registrar.models import Domain, DomainInformation, DomainInvitation, DomainRequest, UserDomainRole

# Constants for clarity
ALL = "all"
IS_STAFF = "is_staff"
IS_DOMAIN_MANAGER = "is_domain_manager"
IS_DOMAIN_REQUEST_CREATOR = "is_domain_request_creator"
IS_STAFF_MANAGING_DOMAIN = "is_staff_managing_domain"
IS_PORTFOLIO_MEMBER = "is_portfolio_member"
IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER = "is_portfolio_member_and_domain_manager"
IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER = "is_domain_manager_and_not_portfolio_member"
HAS_PORTFOLIO_DOMAINS_ANY_PERM = "has_portfolio_domains_any_perm"
HAS_PORTFOLIO_DOMAINS_VIEW_ALL = "has_portfolio_domains_view_all"
HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM = "has_portfolio_domain_requests_any_perm"
HAS_PORTFOLIO_DOMAIN_REQUESTS_VIEW_ALL = "has_portfolio_domain_requests_view_all"
HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT = "has_portfolio_domain_requests_edit"
HAS_PORTFOLIO_MEMBERS_ANY_PERM = "has_portfolio_members_any_perm"
HAS_PORTFOLIO_MEMBERS_EDIT = "has_portfolio_members_edit"
HAS_PORTFOLIO_MEMBERS_VIEW = "has_portfolio_members_view"


def grant_access(*rules):
    """
    Allows multiple rules in a single decorator call:
    @grant_access(IS_STAFF, IS_SUPERUSER, IS_DOMAIN_MANAGER)
    or multiple stacked decorators:
    @grant_access(IS_SUPERUSER)
    @grant_access(IS_DOMAIN_MANAGER)
    """

    def decorator(view):
        if isinstance(view, type):  # If decorating a class-based view (CBV)
            original_dispatch = view.dispatch  # save original dispatch method

            @method_decorator(grant_access(*rules))  # apply the decorator to dispatch
            def wrapped_dispatch(self, request, *args, **kwargs):
                if not _user_has_permission(request.user, request, rules, **kwargs):
                    raise PermissionDenied
                return original_dispatch(self, request, *args, **kwargs)

            view.dispatch = wrapped_dispatch  # replace dispatch with wrapped version
            return view

        else:  # If decorating a function-based view (FBV)
            view.has_explicit_access = True
            existing_rules = getattr(view, "_access_rules", set())
            existing_rules.update(rules)
            view._access_rules = existing_rules

            @functools.wraps(view)
            def wrapper(request, *args, **kwargs):
                if not _user_has_permission(request.user, request, rules, **kwargs):
                    raise PermissionDenied
                return view(request, *args, **kwargs)

            return wrapper

    return decorator


def _user_has_permission(user, request, rules, **kwargs):
    """
    Checks if the user meets the permission requirements.
    """

    # Skip authentication if @login_not_required is applied
    if getattr(request, "login_not_required", False):
        return True

    # Allow everyone if `ALL` is in rules
    if ALL in rules:
        return True

    # Ensure user is authenticated
    if not user.is_authenticated:
        return False

    # Ensure user is not restricted
    if user.is_restricted():
        return False

    conditions_met = []

    if IS_STAFF in rules:
        conditions_met.append(user.is_staff)

    if not any(conditions_met) and IS_DOMAIN_MANAGER in rules:
        has_permission = _is_domain_manager(user, **kwargs)
        conditions_met.append(has_permission)

    if not any(conditions_met) and IS_STAFF_MANAGING_DOMAIN in rules:
        has_permission = _is_staff_managing_domain(request, **kwargs)
        conditions_met.append(has_permission)

    if not any(conditions_met) and IS_PORTFOLIO_MEMBER in rules:
        has_permission = user.is_org_user(request)
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_DOMAINS_VIEW_ALL in rules:
        domain_id = kwargs.get("domain_pk")
        has_permission = _can_access_domain_via_portfolio_view_all_domains(request, domain_id)
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_DOMAINS_ANY_PERM in rules:
        has_permission = user.is_org_user(request) and user.has_any_domains_portfolio_permission(
            request.session.get("portfolio")
        )
        conditions_met.append(has_permission)

    if not any(conditions_met) and IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER in rules:
        has_permission = _is_domain_manager(user, **kwargs) and _is_portfolio_member(request)
        conditions_met.append(has_permission)

    if not any(conditions_met) and IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER in rules:
        has_permission = _is_domain_manager(user, **kwargs) and not _is_portfolio_member(request)
        conditions_met.append(has_permission)

    if not any(conditions_met) and IS_DOMAIN_REQUEST_CREATOR in rules:
        domain_request_id = kwargs.get("domain_request_pk")
        has_permission = _is_domain_request_creator(user, domain_request_id) and not _is_portfolio_member(request)
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM in rules:
        has_permission = user.is_org_user(request) and user.has_any_requests_portfolio_permission(
            request.session.get("portfolio")
        )
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_DOMAIN_REQUESTS_VIEW_ALL in rules:
        has_permission = user.is_org_user(request) and user.has_view_all_domain_requests_portfolio_permission(
            request.session.get("portfolio")
        )
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT in rules:
        domain_request_id = kwargs.get("domain_request_pk")
        has_permission = _has_portfolio_domain_requests_edit(user, request, domain_request_id)
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_MEMBERS_ANY_PERM in rules:
        portfolio = request.session.get("portfolio")
        has_permission = user.is_org_user(request) and (
            user.has_view_members_portfolio_permission(portfolio)
            or user.has_edit_members_portfolio_permission(portfolio)
        )
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_MEMBERS_EDIT in rules:
        portfolio = request.session.get("portfolio")
        has_permission = user.is_org_user(request) and user.has_edit_members_portfolio_permission(portfolio)
        conditions_met.append(has_permission)

    if not any(conditions_met) and HAS_PORTFOLIO_MEMBERS_VIEW in rules:
        portfolio = request.session.get("portfolio")
        has_permission = user.is_org_user(request) and user.has_view_members_portfolio_permission(portfolio)
        conditions_met.append(has_permission)

    return any(conditions_met)


def _has_portfolio_domain_requests_edit(user, request, domain_request_id):
    if domain_request_id and not _is_domain_request_creator(user, domain_request_id):
        return False
    return user.is_org_user(request) and user.has_edit_request_portfolio_permission(request.session.get("portfolio"))


def _is_domain_manager(user, **kwargs):
    """
    Determines if the given user is a domain manager for a specified domain.

    - First, it checks if 'domain_pk' is present in the URL parameters.
    - If 'domain_pk' exists, it verifies if the user has a domain role for that domain.
    - If 'domain_pk' is absent, it checks for 'domain_invitation_pk' to determine if the user has domain permissions through an invitation.

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


def _is_domain_request_creator(user, domain_request_pk):
    """Checks to see if the user is the creator of a domain request
    with domain_request_pk."""
    if domain_request_pk:
        return DomainRequest.objects.filter(creator=user, id=domain_request_pk).exists()
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


def _can_access_domain_via_portfolio_view_all_domains(request, domain_pk):
    """Returns whether the user in the request can access the domain
    via portfolio view all domains permission."""
    # NOTE: determine if in practice this ever needs to be called on its own
    # or if it can be combined with view_managed_domains
    portfolio = request.session.get("portfolio")
    if request.user.has_view_all_domains_portfolio_permission(portfolio):
        if Domain.objects.filter(id=domain_pk).exists():
            domain = Domain.objects.get(id=domain_pk)
            if domain.domain_info.portfolio == portfolio:
                return True
    return False
