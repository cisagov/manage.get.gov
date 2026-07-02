"""Gunicorn configuration.

Loaded by gunicorn in src/run.sh . It is intentionally NOT loaded
by ``manage.py runserver`` or the test runner, so the psycopg2 patching below
only takes effect under gunicorn's gevent workers in deployed environments.

Patches psycopg2 so DB calls cooperate with gevent.

"""

from psycogreen.gevent import patch_psycopg


def post_fork(server, worker):
    """Make psycopg2 cooperate with gevent in each freshly forked worker."""
    patch_psycopg()
    worker.log.info("Made psycopg2 green for gevent (psycogreen)")
