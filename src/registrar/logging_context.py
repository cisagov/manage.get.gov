"""Per-request logging context ContextVars.

Set by `RequestLoggingMiddleware` and read by the `JsonFormatter` so every log
line emitted during a request can be correlated by user, path, and request id.

See docs/developer/dns-error-handling.md for the DNS-hosting field contract.
"""

from contextvars import ContextVar

user_email_var = ContextVar("user_email")  # type: ignore
ip_address_var = ContextVar("ip_address")  # type: ignore
request_path_var = ContextVar("request_path")  # type: ignore
request_id_var = ContextVar("request_id")  # type: ignore


def set_user_log_context(user_email=None, ip_address=None, request_path=None, request_id=None):
    if user_email is not None:
        user_email_var.set(user_email)
    if ip_address is not None:
        ip_address_var.set(ip_address)
    if request_path is not None:
        request_path_var.set(request_path)
    if request_id is not None:
        request_id_var.set(request_id)


def get_user_log_context():
    return {
        "user_email": user_email_var.get(None) or "Anonymous",
        "ip_address": ip_address_var.get(None) or "Unknown IP",
        "request_path": request_path_var.get(None),
        "request_id": request_id_var.get(None),
    }


def clear_user_log_context():
    user_email_var.set(None)
    ip_address_var.set(None)
    request_path_var.set(None)
    request_id_var.set(None)
