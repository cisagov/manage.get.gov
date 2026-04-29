"""
Dev-only view for bypassing login.gov during local E2E regression tests.

This view is ONLY active when both DEBUG=True and ALLOW_AUTO_LOGIN=True are set
in the environment. It is never reachable in sandbox or production environments.
"""

import logging
from django.conf import settings
from django.contrib.auth import login
from django.http import Http404, HttpResponseRedirect
from registrar.models.user import User

logger = logging.getLogger(__name__)

_AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"

## Todo could make this a class and add more restrictions 
# so it continuious checks that environment is correct and 
# returns None if in non local env
# definitely don't leave this as is
def _create_generic_test_user(request):
    """Generic E2E test user — no portfolio, no domains, just a working account.
        Each key maps to a factory function: (request) -> User.
        Factories use get_or_create throughout so they are idempotent.
    """
    user, created = User.objects.get_or_create(
        username="testuser-e2e",
        defaults={
            "email": "testuser-e2e@example.com",
            "first_name": "E2E",
            "last_name": "TestUser",
            "title": "Test Engineer",
            "phone": "+12025550100",
            "is_active": True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
        logger.info("Created generic E2E test user")
    return user


def _create_legacy_user_1(request):
    """
    User 1 — legacy domain manager with no portfolio.

    Setup:
      - 3 domains in READY state (donutdefenders.gov, alienoutpost.gov, alicornalliance.gov)
      - DomainInformation for each with a senior official Contact
      - UserDomainRole(MANAGER) for each domain
      - 1 submitted DomainRequest for sprinkledonut.gov
    """
    # Import here to avoid module-level circular imports
    from registrar.models import (
        Domain,
        DomainInformation,
        DomainRequest,
        UserDomainRole,
    )
    from registrar.models.contact import Contact
    from registrar.models.draft_domain import DraftDomain

    user, created = User.objects.get_or_create(
        username="regressiontest+1",
        defaults={
            "email": "regressiontest+1@gmail.com",
            "first_name": "Regression",
            "last_name": "One",
            "title": "Legacy Domain Manager",
            "phone": "+12025550101",
            "is_active": True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
        logger.info("Created legacy test user 1: %s", user.email)

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


# Map persona query param values to factory functions
# TODO- more reason to have this as a class, below can be the helper
_PERSONAS = {
    "generic": _create_generic_test_user,
    "legacy_user_1": _create_legacy_user_1,
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
      - ALLOW_AUTO_LOGIN is forced False unless DEBUG=True (settings.py).
    """
    if not getattr(settings, "ALLOW_AUTO_LOGIN", False):
        raise Http404("Dev auto-login is not enabled.")

    persona_key = request.GET.get("persona", "generic")
    next_url = request.GET.get("next", "/user-profile")

    factory = _PERSONAS.get(persona_key)
    if factory is None:
        raise Http404(f"Unknown persona: {persona_key!r}. Available: {list(_PERSONAS)}")

    user = factory(request)
    login(request, user, backend=_AUTH_BACKEND)
    logger.info("Auto-logged in persona=%r as %s → %s", persona_key, user.username, next_url)
    return HttpResponseRedirect(next_url)
