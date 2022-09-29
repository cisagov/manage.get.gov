import os
import logging

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

def dont_print_garbage(f):
    """
    Decorator to place on tests to silence console logging.

    This is helpful on tests which trigger console messages
    (such as errors) which are normal and expected.

    It can easily be removed to debug a failing test.
    """
    def wrapper(*args, **kwargs):
        restore = {}
        handlers = get_handlers()
        devnull = open(os.devnull, 'w')

        # redirect all the streams
        for handler in handlers.values():
            prior = handler.setStream(devnull)
            restore[handler.name] = prior
        # run the test
        result = f(*args, **kwargs)
        # restore the streams
        for handler in handlers.values():
            handler.setStream(restore[handler.name])

        return result

    return wrapper
