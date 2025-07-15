from contextvars import ContextVar

user_email_var = ContextVar("user_email")  # type: ignore
ip_address_var = ContextVar("ip_address")  # type: ignore
request_path_var = ContextVar("request_path")  # type: ignore


def set_user_log_context(user_email=None, ip_address=None, request_path=None):
    if user_email is not None:
        user_email_var.set(user_email)
    if ip_address is not None:
        ip_address_var.set(ip_address)
    if request_path is not None:
        request_path_var.set(request_path)


def get_user_log_context():
    return {
        "user_email": user_email_var.get(),
        "ip_address": ip_address_var.get(),
        "request_path": request_path_var.get(),
    }
