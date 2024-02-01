#/bin/bash

set -o errexit
set -o pipefail

# Make sure that django's `collectstatic` has been run locally before pushing up to any environment,
# so that the styles and static assets to show up correctly on any environment.

gunicorn --worker-class=gevent --worker-connections=1000 --workers=1 registrar.config.wsgi -t 60
