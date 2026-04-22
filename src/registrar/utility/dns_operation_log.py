"""Helper for writing DnsOperationLog rows.

Recording failure must never break a user flow, so every write is wrapped in a
broad exception handler that logs but swallows exceptions. If the audit table
is unreachable or mis-migrated, the user's DNS operation still completes.

See docs/developer/dns-error-handling.md.
"""

import logging

from registrar.models.dns.dns_operation_log import DnsOperationLog

logger = logging.getLogger(__name__)


def record_dns_operation(
    *,
    request=None,
    operation: str,
    outcome: str,
    domain_name: str = "",
    dns_account_id: str = "",
    zone_id: str = "",
    record_id: str = "",
    error_code: str = "",
    upstream_status: int | None = None,
    cf_ray: str = "",
    duration_ms: int | None = None,
    user_email: str = "",
    notes: str = "",
) -> None:
    """Write a single DnsOperationLog row. Swallows any DB error."""
    request_id = ""
    if request is not None:
        request_id = getattr(request, "_dns_request_id", "") or ""
        if not user_email and getattr(request, "user", None) is not None:
            user = request.user
            if getattr(user, "is_authenticated", False):
                user_email = getattr(user, "email", "") or ""

    try:
        DnsOperationLog.objects.create(
            operation=operation,
            outcome=outcome,
            user_email=user_email,
            request_id=request_id,
            domain_name=domain_name,
            dns_account_id=dns_account_id,
            zone_id=zone_id,
            record_id=record_id or "",
            error_code=error_code,
            upstream_status=upstream_status,
            cf_ray=cf_ray,
            duration_ms=duration_ms,
            notes=notes,
        )
    except Exception:
        # Recording is best-effort; failure must not break the user flow.
        logger.exception("Failed to write DnsOperationLog row (non-fatal)")
