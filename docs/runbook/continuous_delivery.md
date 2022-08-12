# Cloud.gov Continuous Delivery

We use a [cloud.gov service account](https://cloud.gov/docs/services/cloud-gov-service-account/) to deploy from this repository to cloud.gov with a SpaceDeveloper user.

## Rotating Cloud.gov Secrets

Secrets are set and rotated using the [cloud.gov secret rotation script](./scripts/rotate_cloud_secrets.sh).

Prerequistes for running the script are installations of `jq`, `gh`, and the `cf` CLI tool. 

## Github Action

TBD info about how we are using the github action to deploy.
