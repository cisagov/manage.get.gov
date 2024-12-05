#!/bin/bash

echo "In node_entrypoint.sh"
whoami

# Get UID and GID of the /app directory owner
HOST_UID=$(stat -c '%u' /app)
HOST_GID=$(stat -c '%g' /app)

# Update circleci user's UID and GID to match the host
echo "Updating circleci user and group to match host UID:GID ($HOST_UID:$HOST_GID)"
sudo groupmod -g "$HOST_GID" circleci
sudo usermod -u "$HOST_UID" circleci

# Run command as circleci user. Note that command, run_node_watch.sh, is passed as arg to entrypoint
exec gosu circleci "$@"
