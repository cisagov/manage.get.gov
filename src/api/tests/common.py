import os
import logging

from contextlib import contextmanager
from django.contrib.auth import get_user_model


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
        # close the file we opened
        devnull.close()


def less_console_noise_decorator(func):
    """
    Decorator to silence console logging using the less_console_noise() function.
    """

    # "Wrap" the original function in the less_console_noise with clause,
    # then just return this wrapper.
    def wrapper(*args, **kwargs):
        with less_console_noise():
            return func(*args, **kwargs)

    return wrapper


def create_user():
    username = "restricted_user"
    first_name = "First"
    last_name = "Last"
    email = "restricted@example.com"
    phone = "8003111234"
    title = "title"
    user = get_user_model().objects.create(
        username=username, first_name=first_name, last_name=last_name, email=email, phone=phone, title=title
    )
    return user
