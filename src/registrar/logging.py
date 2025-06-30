import logging
from .thread_locals import get_user, get_ip


class UserFilter(logging.Filter):
    def filter(self, record):
        user = get_user()
        record.email = getattr(user, "email", "anonymous")
        record.ip = get_ip()
        return True
