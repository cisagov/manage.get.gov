import threading

_user_local = threading.local()


def set_log_user(user_email, ip):
    _user_local.user_email = user_email
    _user_local.ip = ip


def get_log_user_email():
    return getattr(_user_local, "user_email", "None")


def get_log_ip():
    return getattr(_user_local, "ip", "Anonymous")
