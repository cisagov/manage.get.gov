import threading

_user_storage = threading.local()


def set_user_email(user):
    _user_storage.user_email = user.email


def get_user():
    return getattr(_user_storage, "user", None)


def set_ip(ip):
    _user_storage.ip = ip


def get_ip():
    return getattr(_user_storage, "ip", None)


