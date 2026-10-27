"""Dev-only endpoints for the Playwright UI tests.

  GET  /api/v1/dev/playwright-seed   → mint test data + a session
  POST /api/v1/dev/playwright-purge  → delete that test data + sessions

URLs are only registered when IS_PRODUCTION is False
(see registrar/config/urls.py); the views also 404 as a safety net.
"""

import json
from io import StringIO

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from registrar.management.commands.seed_playwright_session import (
    TEST_DOMAIN_NAME,
    TEST_USERNAME,
)
from registrar.models import (
    User,
    )


@require_GET
def playwright_seed(request):
    """Returns key=value lines (eval-friendly) or JSON with ?format=json."""
    if settings.IS_PRODUCTION:
        raise Http404

    out = StringIO()
    call_command("seed_playwright_session", stdout=out)

    seed = None
    for line in out.getvalue().splitlines():
        if line.startswith("PLAYWRIGHT_SEED_JSON="):
            seed = json.loads(line.split("=", 1)[1])
            break
    if seed is None:
        return HttpResponse("seed command produced no output", status=500)

    if request.GET.get("format") == "json":
        return JsonResponse(seed)

    body = (
        f"SESSION_KEY={seed['sessionKey']}\n"
    )
    return HttpResponse(body, content_type="text/plain")


# csrf_exempt: POST without a session can't carry a CSRF token. Safe
# because the URL is dev-only (only registered when IS_PRODUCTION is
# False) and the work is bounded to the seeded test rows.
@csrf_exempt
@require_POST
@transaction.atomic
def playwright_purge(request):
    """Delete the user/domain/DNS rows + sessions seeded by playwright_seed.

    Safe to re-run — silent no-op if any of the rows are already gone.
    """
    if settings.IS_PRODUCTION:
        raise Http404

    user = User.objects.filter(username=TEST_USERNAME).first()
    if user:
        # Sessions don't FK to User; scan and decode to find this user's.
        for session in Session.objects.all():
            if session.get_decoded().get("_auth_user_id") == str(user.pk):
                session.delete()
        user.delete()

    return HttpResponse("ok\n", content_type="text/plain")
