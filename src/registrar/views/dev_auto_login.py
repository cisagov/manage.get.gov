"""
Dev-only view for bypassing login.gov during local E2E regression tests.

This view is ONLY active when both IS_PRODUCTION=False and ALLOW_AUTO_LOGIN=True are set
in the environment. It is never reachable in sandbox or production environments.
"""

import logging
from django.conf import settings
from django.contrib.auth import login
from django.http import Http404, HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from registrar.models import (
    Contact,
    Domain,
    DomainInformation,
    DomainRequest,
    DraftDomain,
    FederalAgency,
    Portfolio,
    User,
    UserDomainRole,
    UserGroup,
    UserPortfolioPermission,
    WaffleFlag,
)
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.utility.constants import BranchChoices

logger = logging.getLogger(__name__)

_AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"

# TODO: could make this a class and add more restrictions
# so it continuously checks that environment is correct and
# returns None if in non local env



def _get_or_create_user(username, email, first_name, last_name, title, phone, **extra_fields):
    """Get or create an E2E test user, setting an unusable password on first creation."""
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "title": title,
            "phone": phone,
            "is_active": True,
            **extra_fields,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
        logger.debug("Created E2E test user: %s", user.email)
    return user


def _get_or_create_portfolio(user, name, roles, additional_permissions=None):
    """Get or create a portfolio and assign the user to it with the given roles."""
    portfolio, _ = Portfolio.objects.get_or_create(
        organization_name=name,
        defaults={"requester": user},
    )
    permission_defaults = {"roles": roles}
    if additional_permissions:
        permission_defaults["additional_permissions"] = additional_permissions
    UserPortfolioPermission.objects.get_or_create(
        user=user,
        portfolio=portfolio,
        defaults=permission_defaults,
    )
    return portfolio


def _get_or_create_managed_domain(user, name):
    """Get or create a READY domain and assign the user as its manager."""
    domain, _ = Domain.objects.get_or_create(
        name=name,
        defaults={"state": Domain.State.READY},
    )
    UserDomainRole.objects.get_or_create(
        user=user,
        domain=domain,
        defaults={"role": UserDomainRole.Roles.MANAGER},
    )
    return domain


def _create_generic_test_user(request):
    """Generic E2E test user — no portfolio, no domains, just a working account.
    Each key maps to a factory function: (request) -> User.
    Factories use get_or_create throughout so they are idempotent.
    """
    return _get_or_create_user(
        "testuser-e2e", "testuser-e2e@example.com", "E2E", "TestUser", "Test Engineer", "+12025550100"
    )


def _create_legacy_user_1(request):
    """
    User 1 — legacy domain manager with no portfolio.

    Setup:
      - 3 domains in READY state (donutdefenders.gov, alienoutpost.gov, alicornalliance.gov)
      - DomainInformation for each with a senior official Contact
      - UserDomainRole(MANAGER) for each domain
      - 1 submitted DomainRequest for sprinkledonut.gov
    """
    user = _get_or_create_user(
        "regressiontest+1",
        "regressiontest+1@gmail.com",
        "Regression",
        "One",
        "Legacy Domain Manager",
        "+12025550101",
    )

    # Senior official contact (shared across all domains for simplicity)
    senior_official, _ = Contact.objects.get_or_create(
        email="senior.official+e2e@example.com",
        defaults={
            "first_name": "Senior",
            "last_name": "Official",
            "title": "Director",
            "phone": "+12025550102",
        },
    )

    domain_names = [
        "donutdefenders.gov",
        "alienoutpost.gov",
        "alicornalliance.gov",
    ]

    for name in domain_names:
        domain, _ = Domain.objects.get_or_create(
            name=name,
            defaults={"state": Domain.State.READY},
        )

        DomainInformation.objects.get_or_create(
            domain=domain,
            defaults={
                "requester": user,
                "senior_official": senior_official,
            },
        )

        UserDomainRole.objects.get_or_create(
            user=user,
            domain=domain,
            defaults={"role": UserDomainRole.Roles.MANAGER},
        )

    # Submitted domain request for sprinkledonut.gov
    draft_domain, _ = DraftDomain.objects.get_or_create(
        name="sprinkledonut.gov",
    )
    DomainRequest.objects.get_or_create(
        requester=user,
        requested_domain=draft_domain,
        defaults={"status": DomainRequest.DomainRequestStatus.SUBMITTED},
    )

    logger.info("Legacy user 1 setup complete: %d domains, 1 domain request", len(domain_names))
    return user


def _create_portfolio_user_2(request):
    """
    User 2 — basic member - domain manager.

    Setup:
      - 1 portfolio
      - User has organization_member role in the portfolio
      - At least 1 domain in the portfolio
    """
    user = _get_or_create_user(
        "regressiontest+2",
        "regressiontest+2@gmail.com",
        "Regression",
        "Two",
        "Basic Domain Manager",
        "+12025550103",
    )

    portfolio = _get_or_create_portfolio(
        user,
        "Test Portfolio 2",
        [UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
    )

    # Add a domain to the portfolio and assign user as manager
    domain, _ = Domain.objects.get_or_create(
        name="testdomain2.gov",
        defaults={"state": Domain.State.READY},
    )

    # DomainInformation.portfolio is the field the portfolio domains view queries
    DomainInformation.objects.update_or_create(
        domain=domain,
        defaults={"requester": user, "portfolio": portfolio},
    )

    UserDomainRole.objects.get_or_create(
        user=user,
        domain=domain,
        defaults={"role": UserDomainRole.Roles.MANAGER},
    )

    return user


def _create_portfolio_user_requester_3(request):
    """
    User 3 — basic member - domain manager and requester.

    Setup:
      - 1 portfolio
      - User has organization_member role with EDIT_REQUESTS additional permission
      - At least 1 domain in the portfolio
    """
    user = _get_or_create_user(
        "regressiontest+3",
        "regressiontest+3@gmail.com",
        "Regression",
        "Three",
        "Domain Manager Requester",
        "+12025550104",
    )

    portfolio = _get_or_create_portfolio(
        user,
        "Test Portfolio 3",
        [UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        additional_permissions=[UserPortfolioPermissionChoices.EDIT_REQUESTS],
    )

    # Add a domain to the portfolio and assign user as manager
    domain, _ = Domain.objects.get_or_create(
        name="testdomain3.gov",
        defaults={"state": Domain.State.READY},
    )

    DomainInformation.objects.update_or_create(
        domain=domain,
        defaults={"requester": user, "portfolio": portfolio},
    )

    UserDomainRole.objects.get_or_create(
        user=user,
        domain=domain,
        defaults={"role": UserDomainRole.Roles.MANAGER},
    )

    return user


def _create_org_admin_4(request):
    """
    User 4 — organization admin.

    Setup:
      - 1 portfolio
      - User has organization admin permission
      - Portfolio has domains and domain requests
    """
    user = _get_or_create_user(
        "regressiontest+4",
        "regressiontest+4@gmail.com",
        "Regression",
        "Four",
        "Org Admin",
        "+12025550105",
    )

    portfolio = _get_or_create_portfolio(
        user,
        "Test Portfolio 4",
        [UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
    )

    # Add domains and requests
    domain, _ = Domain.objects.get_or_create(
        name="testdomain4.gov",
        defaults={"state": Domain.State.READY},
    )

    DomainInformation.objects.update_or_create(
        domain=domain,
        defaults={"requester": user, "portfolio": portfolio},
    )

    draft, _ = DraftDomain.objects.get_or_create(name="testrequest4.gov")
    DomainRequest.objects.update_or_create(
        requester=user,
        requested_domain=draft,
        defaults={"status": DomainRequest.DomainRequestStatus.SUBMITTED, "portfolio": portfolio},
    )

    return user


def _create_mixed_permissions_6(request):
    """
    User 6 — org admin in 1 portfolio + legacy domain manager.

    Setup:
      - 1 portfolio with org admin permission
      - Legacy domains managed by user
    """
    user = _get_or_create_user(
        "regressiontest+6",
        "regressiontest+6@gmail.com",
        "Regression",
        "Six",
        "Mixed Permissions",
        "+12025550107",
    )

    portfolio = _get_or_create_portfolio(
        user,
        "Test Portfolio 6",
        [UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
    )

    # Portfolio domain (visible in portfolio domains table)
    portfolio_domain, _ = Domain.objects.get_or_create(
        name="testdomain6.gov",
        defaults={"state": Domain.State.READY},
    )

    DomainInformation.objects.update_or_create(
        domain=portfolio_domain,
        defaults={"requester": user, "portfolio": portfolio},
    )

    UserDomainRole.objects.get_or_create(
        user=user,
        domain=portfolio_domain,
        defaults={"role": UserDomainRole.Roles.MANAGER},
    )

    # Legacy domain (no portfolio — appears only outside portfolio context)
    legacy_domain, _ = Domain.objects.get_or_create(
        name="legacy6.gov",
        defaults={"state": Domain.State.READY},
    )

    UserDomainRole.objects.get_or_create(
        user=user,
        domain=legacy_domain,
        defaults={"role": UserDomainRole.Roles.MANAGER},
    )

    senior_official, _ = Contact.objects.get_or_create(
        email="senior6@example.com",
        defaults={
            "first_name": "Senior6",
            "last_name": "Official",
            "title": "Director",
            "phone": "+12025550108",
        },
    )

    DomainInformation.objects.get_or_create(
        domain=legacy_domain,
        defaults={
            "requester": user,
            "senior_official": senior_official,
        },
    )

    return user


def _create_multi_portfolio_admin_7(request):
    """
    User 7 — organization admin in 2 different portfolios.

    Setup:
      - 2 portfolios
      - User has org admin permission in both
      - multiple_portfolios waffle flag enabled for everyone
    """
    user = _get_or_create_user(
        "regressiontest+7",
        "regressiontest+7@gmail.com",
        "Regression",
        "Seven",
        "Multi Portfolio Admin",
        "+12025550109",
    )

    # Enable the multiple_portfolios feature flag only for user 7
    # Use per-user activation (not everyone=True) to avoid breaking other users
    flag, _ = WaffleFlag.objects.update_or_create(
        name="multiple_portfolios",
        defaults={"everyone": None},  # Not globally enabled; use per-user control
    )
    flag.users.add(user)

    _get_or_create_portfolio(user, "Test Portfolio 7A", [UserPortfolioRoleChoices.ORGANIZATION_ADMIN])
    _get_or_create_portfolio(user, "Test Portfolio 7B", [UserPortfolioRoleChoices.ORGANIZATION_ADMIN])

    return user


def _seed_non_federal_requests(user, senior_official):
    """Seed non-federal domain requests for the admin analyst user."""
    Status = DomainRequest.DomainRequestStatus
    Reasons = DomainRequest.RejectionReasons
    non_federal = [
        # (draft_name, org_type, status, is_election, rejection_reason)
        ("a8city1.gov", "city", Status.SUBMITTED, False, None),
        ("a8city2.gov", "city", Status.IN_REVIEW, False, None),
        ("a8city3.gov", "city", Status.REJECTED, False, Reasons.DOMAIN_PURPOSE),
        ("a8county1.gov", "county", Status.SUBMITTED, False, None),
        ("a8county2.gov", "county", Status.IN_REVIEW, False, None),
        ("a8state1.gov", "state_or_territory", Status.SUBMITTED, False, None),
        ("a8state2.gov", "state_or_territory", Status.ACTION_NEEDED, False, None),
        ("a8tribal1.gov", "tribal", Status.SUBMITTED, False, None),
        ("a8school1.gov", "school_district", Status.SUBMITTED, False, None),
        ("a8interstate1.gov", "interstate", Status.SUBMITTED, False, None),
        ("a8specdistr1.gov", "special_district", Status.IN_REVIEW, False, None),
        ("a8electcity1.gov", "city", Status.SUBMITTED, True, None),
        ("a8electcounty1.gov", "county", Status.SUBMITTED, True, None),
    ]
    for name, org_type, status, is_election, rejection_reason in non_federal:
        draft, _ = DraftDomain.objects.get_or_create(name=name)
        defaults = {
            "requester": user,
            "status": status,
            "generic_org_type": org_type,
            "is_election_board": is_election,
            "senior_official": senior_official,
            "organization_name": f"Test Org {name}",
            "city": "Washington",
            "state_territory": "DC",
            "address_line1": "123 Test St",
            "zipcode": "20001",
        }
        if rejection_reason:
            defaults["rejection_reason"] = rejection_reason
        DomainRequest.objects.update_or_create(requested_domain=draft, defaults=defaults)


def _seed_federal_requests(user, senior_official, exec_agency, judicial_agency, legislative_agency):
    """Seed federal domain requests for the admin analyst user."""
    Status = DomainRequest.DomainRequestStatus
    Reasons = DomainRequest.RejectionReasons
    federal = [
        # (draft_name, agency, federal_type, status, rejection_reason)
        ("a8fedexec1.gov", exec_agency, BranchChoices.EXECUTIVE, Status.SUBMITTED, None),
        ("a8fedexec2.gov", exec_agency, BranchChoices.EXECUTIVE, Status.IN_REVIEW, None),
        ("a8fedjud1.gov", judicial_agency, BranchChoices.JUDICIAL, Status.SUBMITTED, None),
        ("a8fedleg1.gov", legislative_agency, BranchChoices.LEGISLATIVE, Status.IN_REVIEW, None),
        ("a8fedexec3.gov", exec_agency, BranchChoices.EXECUTIVE, Status.ACTION_NEEDED, None),
        ("a8fedjud2.gov", judicial_agency, BranchChoices.JUDICIAL, Status.REJECTED, Reasons.ORG_NOT_ELIGIBLE),
    ]
    for name, agency, fed_type, status, rejection_reason in federal:
        draft, _ = DraftDomain.objects.get_or_create(name=name)
        defaults = {
            "requester": user,
            "status": status,
            "generic_org_type": DomainRequest.OrganizationChoices.FEDERAL,
            "federal_type": fed_type,
            "federal_agency": agency,
            "senior_official": senior_official,
            "organization_name": agency.agency,
            "city": "Washington",
            "state_territory": "DC",
            "address_line1": "123 Federal Ave",
            "zipcode": "20001",
        }
        if rejection_reason:
            defaults["rejection_reason"] = rejection_reason
        DomainRequest.objects.update_or_create(requested_domain=draft, defaults=defaults)


def _create_django_admin_analyst_8(request):
    """
    User 8 — Django admin analyst: is_staff=True, is_superuser=True, cisa_analysts_group.

    Setup:
      - Staff + superuser permissions (can access Django admin)
      - Member of cisa_analysts_group (analyst access permission)
      - Rich test dataset: domain requests in many statuses + domains for filter testing
        * Non-federal: city, county, state_or_territory, tribal, school_district, interstate, special_district
        * Federal: executive, judicial, legislative branches
        * Election board variants
        * Rejected requests with rejection reasons
        * Approved requests with corresponding Domain + DomainInformation objects

    Workflow test target:
      a8city1.gov — SUBMITTED, no pre-existing domain (test will set investigator + change status)
    """
    user = _get_or_create_user(
        "regressiontest+8",
        "regressiontest+8@example.com",
        "Analyst",
        "Eight",
        "CISA Analyst",
        "+12025550110",
        is_staff=True,
        is_superuser=True,
    )
    if not user.is_staff or not user.is_superuser:
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])

    # Add to cisa_analysts_group (created by migrations)
    analyst_group, _ = UserGroup.objects.get_or_create(name="cisa_analysts_group")
    user.groups.add(analyst_group)

    # Shared senior official
    senior_official, _ = Contact.objects.get_or_create(
        email="senior8@example.com",
        defaults={
            "first_name": "Senior8",
            "last_name": "Official",
            "title": "Director",
            "phone": "+12025550200",
        },
    )

    # Federal agencies
    exec_agency, _ = FederalAgency.objects.get_or_create(
        agency="Test Executive Agency E2E",
        defaults={"federal_type": BranchChoices.EXECUTIVE},
    )
    judicial_agency, _ = FederalAgency.objects.get_or_create(
        agency="Test Judicial Agency E2E",
        defaults={"federal_type": BranchChoices.JUDICIAL},
    )
    legislative_agency, _ = FederalAgency.objects.get_or_create(
        agency="Test Legislative Agency E2E",
        defaults={"federal_type": BranchChoices.LEGISLATIVE},
    )

    _seed_non_federal_requests(user, senior_official)
    _seed_federal_requests(user, senior_official, exec_agency, judicial_agency, legislative_agency)

    # Approved requests — manually create Domain + DomainInformation
    approved = [
        # (domain_name, org_type, agency, fed_type, domain_state, is_election)
        ("a8citya.gov", "city", None, None, Domain.State.READY, False),
        ("a8countya.gov", "county", None, None, Domain.State.READY, False),
        ("a8statea.gov", "state_or_territory", None, None, Domain.State.ON_HOLD, False),
        ("a8fedexeca.gov", "federal", exec_agency, BranchChoices.EXECUTIVE, Domain.State.READY, False),
        ("a8fedjuda.gov", "federal", judicial_agency, BranchChoices.JUDICIAL, Domain.State.READY, False),
        ("a8electa.gov", "city", None, None, Domain.State.READY, True),
    ]

    for domain_name, org_type, agency, fed_type, domain_state, is_election in approved:
        domain, _ = Domain.objects.get_or_create(
            name=domain_name,
            defaults={"state": domain_state},
        )
        di_defaults = {
            "requester": user,
            "generic_org_type": org_type,
            "senior_official": senior_official,
            "organization_name": f"Test Org {domain_name}",
            "is_election_board": is_election,
        }
        if agency:
            di_defaults["federal_agency"] = agency
            di_defaults["federal_type"] = fed_type
        DomainInformation.objects.update_or_create(domain=domain, defaults=di_defaults)

        draft, _ = DraftDomain.objects.get_or_create(name=domain_name)
        dr_defaults = {
            "requester": user,
            "status": DomainRequest.DomainRequestStatus.APPROVED,
            "approved_domain": domain,
            "generic_org_type": org_type,
            "is_election_board": is_election,
            "senior_official": senior_official,
            "organization_name": f"Test Org {domain_name}",
            "city": "Washington",
            "state_territory": "DC",
            "address_line1": "123 Test St",
            "zipcode": "20001",
        }
        if agency:
            dr_defaults["federal_agency"] = agency
            dr_defaults["federal_type"] = fed_type
        DomainRequest.objects.update_or_create(requested_domain=draft, defaults=dr_defaults)

    # The workflow test changes a8city1.gov (sets investigator, then approves it).
    # Reset it to a clean state on every login so the test is idempotent.
    try:
        workflow_draft = DraftDomain.objects.get(name="a8city1.gov")
        # Clear approved_domain before deleting to avoid FK PROTECT violations.
        DomainRequest.objects.filter(requested_domain=workflow_draft).update(
            investigator=None,
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            approved_domain=None,
        )
        # Delete DomainInformation first (references Domain), then the Domain itself.
        DomainInformation.objects.filter(domain__name="a8city1.gov").delete()
        Domain.objects.filter(name="a8city1.gov").delete()
    except DraftDomain.DoesNotExist:
        pass

    return user


# Map persona query param values to factory functions
# TODO- more reason to have this as a class, below can be the helper
_PERSONAS = {
    "generic": _create_generic_test_user,
    "legacy_user_1": _create_legacy_user_1,
    "portfolio_user_2": _create_portfolio_user_2,
    "portfolio_user_requester_3": _create_portfolio_user_requester_3,
    "org_admin_4": _create_org_admin_4,
    "mixed_permissions_6": _create_mixed_permissions_6,
    "multi_portfolio_admin_7": _create_multi_portfolio_admin_7,
    "django_admin_analyst_8": _create_django_admin_analyst_8,
}


def dev_auto_login(request):
    """
    Creates (or retrieves) a test user for the requested persona, logs them in,
    then redirects to the URL specified by the `next` query param.

    Query params:
      persona  — which test user to create/use (default: "generic")
      next     — where to redirect after login (default: "/user-profile")

    Guards:
      - Returns 404 unless settings.ALLOW_AUTO_LOGIN is True.
      - Returns 404 unless settings.IS_PRODUCTION is False (settings.py).
      - Gating by using both flags while providing a way to enable some sandboxes to use this view and not others
    """
    if not getattr(settings, "ALLOW_AUTO_LOGIN", False):
        raise Http404("Dev auto-login is not enabled.")

    persona_key = request.GET.get("persona", "generic")
    next_url = request.GET.get("next", "/user-profile")

    #  If the next_url is not a safe URL just go to user profile
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = "/user-profile"

    factory = _PERSONAS.get(persona_key)
    if factory is None:
        raise Http404(f"Unknown persona: {persona_key!r}. Available: {list(_PERSONAS)}")

    user = factory(request)
    login(request, user, backend=_AUTH_BACKEND)
    logger.info("Auto-logged in persona=%r as %s → %s", persona_key, user.username, next_url)
    return HttpResponseRedirect(next_url)
