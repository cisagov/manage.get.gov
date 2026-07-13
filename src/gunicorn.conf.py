"""Gunicorn configuration.

Loaded by gunicorn in src/run.sh . It is intentionally NOT loaded
by ``manage.py runserver`` or the test runner, so the psycopg2 patching below
only takes effect under gunicorn's gevent workers in deployed environments.

Patches psycopg2 so DB calls cooperate with gevent.

"""

from psycogreen.gevent import patch_psycopg


def post_fork(server, worker):
    """Make psycopg2 cooperate with gevent in each freshly forked worker.

    Gunicorn calls it inside each worker process right after that worker
    is forked from the master process.

    Our workers use gevent, which handles many requests at once by switching
    away from any request that's waiting (say, on the database) so the others
    keep moving. psycopg2 (our Postgres driver) doesn't do that on its own — a
    single query would freeze the whole worker until it finished.

    patch_psycopg() fixes that: it teaches psycopg2 to pause politely and let
    other requests run while it waits on the database. We do it here, inside
    each worker, because every worker is its own process and needs its own fix
    """
    patch_psycopg()
    worker.log.info("Made psycopg2 green for gevent (psycogreen)")
