#!/bin/bash

# Get UID and GID of the /app directory owner
HOST_UID=$(stat -c '%u' /app)
HOST_GID=$(stat -c '%g' /app)

# Update circleci user's UID and GID to match the host
echo "Updating circleci user and group to match host UID:GID ($HOST_UID:$HOST_GID)"
sudo groupmod -g "$HOST_GID" circleci
sudo usermod -u "$HOST_UID" circleci

exec gosu circleci "$@"
