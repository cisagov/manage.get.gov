import threading

_user_local = threading.local()


def set_log_user(user_email, ip, request_path):
    _user_local.user_email = user_email
    _user_local.ip = ip
    _user_local.request_path = request_path


def get_log_user_email():
    return getattr(_user_local, "user_email", None)


def get_log_ip():
    return getattr(_user_local, "ip", None)


def get_request_path():
    return getattr(_user_local, "request_path", None)
