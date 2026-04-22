"""JSON response envelopes for DNS-hosting API endpoints.

See docs/developer/dns-error-handling.md for the envelope contract.

The canonical shape is:

    {"status": "error", "code": "DNS_*", "message": "...", "request_id": "..."}

HTTP status is derived from the error code's severity unless explicitly
overridden. `request_id` is pulled from `request._dns_request_id`, which
`RequestLoggingMiddleware` sets on every incoming request.
"""

from django.http import JsonResponse

from registrar.utility.errors import DnsHostingError, DnsHostingErrorCodes

_HTTP_STATUS_BY_CODE = {
    DnsHostingErrorCodes.ZONE_NOT_FOUND: 400,
    DnsHostingErrorCodes.RECORD_CONFLICT: 409,
    DnsHostingErrorCodes.VALIDATION_FAILED: 400,
    DnsHostingErrorCodes.RATE_LIMIT_EXCEEDED: 429,
    DnsHostingErrorCodes.AUTH_FAILED: 502,
    DnsHostingErrorCodes.UPSTREAM_TIMEOUT: 504,
    DnsHostingErrorCodes.UPSTREAM_ERROR: 502,
    DnsHostingErrorCodes.UNKNOWN: 500,
}


def get_request_id(request) -> str | None:
    """Read the per-request correlation ID that RequestLoggingMiddleware stashed.

    Returns None if the middleware hasn't run (e.g., unit tests that don't
    route through the middleware stack).
    """
    return getattr(request, "_dns_request_id", None) if request is not None else None


def dns_error_response(exc: DnsHostingError, *, request=None, status: int | None = None) -> JsonResponse:
    """Build the canonical DNS API error envelope for a typed DNS exception."""
    return JsonResponse(
        {
            "status": "error",
            "code": exc.wire_code,
            "message": exc.message,
            "request_id": get_request_id(request),
        },
        status=status or _HTTP_STATUS_BY_CODE.get(exc.code, 500),
    )
