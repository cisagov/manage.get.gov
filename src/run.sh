#/bin/bash

set -o errexit
set -o pipefail

# Only run migrations on the zeroth index when in a cloud.gov environment
if [[ -v CF_INSTANCE_INDEX && $CF_INSTANCE_INDEX == 0 ]]
then
  python manage.py migrate --settings=registrar.config.settings --noinput
else
  echo "Migrations did not run."
  if [[ -v CF_INSTANCE_INDEX ]]
  then
    echo "CF Instance Index is ${CF_INSTANCE_INDEX}."
  fi
fi

# Make sure that django's `collectstatic` has been run locally before pushing up to unstable,
# so that the styles and static assets to show up correctly on unstable.

gunicorn registrar.config.wsgi -t 60
