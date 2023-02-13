import os
import logging

from contextlib import contextmanager
from unittest.mock import Mock
from typing import List, Dict

from django.conf import settings
from django.contrib.auth import get_user_model, login


def get_handlers():
    """Obtain pointers to all StreamHandlers."""
    handlers = {}

    rootlogger = logging.getLogger()
    for h in rootlogger.handlers:
        if isinstance(h, logging.StreamHandler):
            handlers[h.name] = h

    for logger in logging.Logger.manager.loggerDict.values():
        if not isinstance(logger, logging.PlaceHolder):
            for h in logger.handlers:
                if isinstance(h, logging.StreamHandler):
                    handlers[h.name] = h

    return handlers


@contextmanager
def less_console_noise():
    """
    Context manager to use in tests to silence console logging.

    This is helpful on tests which trigger console messages
    (such as errors) which are normal and expected.

    It can easily be removed to debug a failing test.
    """
    restore = {}
    handlers = get_handlers()
    devnull = open(os.devnull, "w")

    # redirect all the streams
    for handler in handlers.values():
        prior = handler.setStream(devnull)
        restore[handler.name] = prior
    try:
        # run the test
        yield
    finally:
        # restore the streams
        for handler in handlers.values():
            handler.setStream(restore[handler.name])


class MockUserLogin:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_anonymous:
            user = None
            UserModel = get_user_model()
            username = "Testy"
            args = {
                UserModel.USERNAME_FIELD: username,
            }
            user, _ = UserModel.objects.get_or_create(**args)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            backend = settings.AUTHENTICATION_BACKENDS[-1]
            login(request, user, backend=backend)

        response = self.get_response(request)
        return response


class MockSESClient(Mock):

    EMAILS_SENT: List[Dict] = []

    def send_email(self, *args, **kwargs):
        self.EMAILS_SENT.append({"args": args, "kwargs": kwargs})
