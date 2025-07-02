import threading

_user_storage = threading.local()


def set_user_email(email):
    _user_storage.user_email = email


def get_user_email():
    return _user_storage.user_email


def set_ip(ip):
    _user_storage.ip = ip


def get_ip():
    return _user_storage.ip
