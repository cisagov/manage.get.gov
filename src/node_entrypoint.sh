#!/bin/bash

# Get UID and GID of the /app directory owner
HOST_UID=$(stat -c '%u' /app)
HOST_GID=$(stat -c '%g' /app)

# Update circleci user's UID and GID to match the host
echo "Updating circleci user and group to match host UID:GID ($HOST_UID:$HOST_GID)"
groupmod -g "$HOST_GID" circleci
usermod -u "$HOST_UID" circleci

echo "Updating ownership of /app recursively to circleci:circleci"
chown -R circleci:circleci /app

# Run command as circleci user. Note that command, run_node_watch.sh, is passed as arg to entrypoint
echo "Switching to circleci user and running command: $@"
su -s /bin/bash -c "$*" circleci
