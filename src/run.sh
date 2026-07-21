#/bin/bash

set -o errexit
set -o pipefail

# Make sure that django's `collectstatic` has been run locally before pushing up to any environment,
# so that the styles and static assets to show up correctly on any environment.

# -c gunicorn.conf.py loads the post_fork hook that patches psycopg2 for gevent
# (psycogreen) so DB calls yield to the event loop instead of blocking the worker.
gunicorn -c gunicorn.conf.py --workers=3 --worker-class=gevent registrar.config.wsgi -t 60
