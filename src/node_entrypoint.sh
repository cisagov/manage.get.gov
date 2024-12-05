#!/bin/bash

# Get UID and GID of the /app directory owner
HOST_UID=$(stat -c '%u' /app)
HOST_GID=$(stat -c '%g' /app)

# Check if the circleci user exists
if id "circleci" &>/dev/null; then
  echo "circleci user exists. Updating UID and GID to match host UID:GID ($HOST_UID:$HOST_GID)"

  # Update circleci user's UID and GID
  groupmod -g "$HOST_GID" circleci
  usermod -u "$HOST_UID" circleci

  echo "Updating ownership of /app recursively to circleci:circleci"
  chown -R circleci:circleci /app

  # Switch to circleci user and execute the command
  echo "Switching to circleci user and running command: $@"
  su -s /bin/bash -c "$*" circleci
else
  echo "circleci user does not exist. Running command as the current user."
  exec "$@"
fi
