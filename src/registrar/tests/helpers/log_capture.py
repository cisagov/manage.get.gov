import io
import json
import logging
from contextlib import contextmanager

from registrar.config.settings import JsonFormatter


@contextmanager
def capture_json_logs(logger_name, level=logging.DEBUG):
    """
    Attach a JSONFormatter'd handler to a logger and capture its live-formatted output.

    Needed instead of assertLogs because assertLogs replaces the logger's
    handlers entirely, and because reformatting captured records after the
    fact would run after any logging contextvars (e.g. domain_name) have
    already been reset.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    original_level = logger.level
    logger.setLevel(level)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()


def json_log_entries(stream, containing=None):
    """
    Parse captured JSON log lines, optionally filtered to those containing a substring.
    """
    entries = []
    for line in stream.getvalue().splitlines():
        if not line.strip():
            continue
        if containing and containing not in line:
            continue
        entries.append(json.loads(line))
    return entries
