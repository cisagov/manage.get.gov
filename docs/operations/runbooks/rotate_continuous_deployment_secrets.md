# HOWTO Rotate Cloud.gov Secrets
========================

These are the secrets GitHub uses to access Cloud.gov during continuous deployment.

Make sure that you have cf v7 and not cf v8 as it will not work with this script. 

Secrets are set and rotated using the [cloud.gov secret rotation script](../../../ops/scripts/rotate_cloud_secrets.sh).

Prerequisites for running the script are installations of `jq`, `gh`, and the `cf` CLI tool. 

NOTE: Secrets must be rotated every 90 days. This script can be used for that routine rotation or it can be used to revoke and re-create tokens if they are compromised.
