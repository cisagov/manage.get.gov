def get_request_id(request) -> str | None:
    """Read the per-request correlation ID that RequestLoggingMiddleware stashed.

    Returns None if the middleware hasn't run (e.g., unit tests that don't
    route through the middleware stack).
    """
    return getattr(request, "_dns_request_id", None) if request is not None else None