#/bin/bash

set -o errexit
set -o pipefail

# Make sure that django's `collectstatic` has been run locally before pushing up to unstable,
# so that the styles and static assets to show up correctly on unstable.

gunicorn registrar.config.wsgi -t 60
