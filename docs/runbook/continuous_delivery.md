# Cloud.gov Continuous Delivery

We use a [cloud.gov service account](https://cloud.gov/docs/services/cloud-gov-service-account/) to deploy from this repository to cloud.gov with a SpaceDeveloper user.

## Rotating Cloud.gov Secrets

Make sure that you have cf v7 and not cf v8 as it will not work with this script. 

Secrets are set and rotated using the [cloud.gov secret rotation script](./scripts/rotate_cloud_secrets.sh).

Prerequistes for running the script are installations of `jq`, `gh`, and the `cf` CLI tool. 

NOTE: Secrets must be rotated every 90 days. This script can be used for that routine rotation or it can be used to revoke and re-create tokens if they are compromised.

## Github Action

TBD info about how we are using the github action to deploy.
