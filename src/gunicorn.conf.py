"""Gunicorn configuration.

Loaded by gunicorn in src/run.sh . It is intentionally NOT loaded
by ``manage.py runserver`` or the test runner, so the psycopg2 patching below
only takes effect under gunicorn's gevent workers in deployed environments.

Why this exists::
``psycopg2`` is a C extension but gevent does not work with C extensions. So while a worker waits
on PostgreSQL it blocks the entire OS thread, stalling every other greenlet on
that worker (they cannot run until the DB call returns).

"""

from psycogreen.gevent import patch_psycopg


def post_fork(server, worker):
    """Make psycopg2 cooperate with gevent in each freshly forked worker."""
    patch_psycopg()
    worker.log.info("Made psycopg2 green for gevent (psycogreen)")
