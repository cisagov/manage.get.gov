import logging
from .thread_locals import get_user_email, get_ip


class UserFilter(logging.Filter):
    def filter(self, record):
        record.email = get_user_email()
        record.ip = get_ip()
        return True
