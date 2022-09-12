# Operations
========================

Some basic information and setup steps are included in this README.

Instructions for specific actions can be found in our [runbooks](./runbooks/).

## Continuous Delivery

We use a [cloud.gov service account](https://cloud.gov/docs/services/cloud-gov-service-account/) to deploy from this repository to cloud.gov with a SpaceDeveloper user.

## Authenticating to Cloud.gov via the command line

You'll need the [Cloud Foundry CLI](https://docs.cloud.gov/getting-started/setup/).

We use the V7 Cloud Foundry CLI.

```shell
cf login -a api.fr.cloud.gov --sso
```

After authenticating, make sure you are targeting the correct org and space!

```bash
cf spaces
cf target -o <ORG> -s <SPACE>
```

## Database

In sandbox, created with `cf create-service aws-rds micro-psql getgov-ENV-database`.

Binding the database in `manifest-<ENVIRONMENT>.json` automatically inserts the connection string into the environment as `DATABASE_URL`.

[Cloud.gov RDS documentation](https://cloud.gov/docs/services/relational-database/).

# Deploy

We have two environments: `unstable` and `staging`. Developers can deploy locally to unstable whenever they want. However, only our CD service can deploy to `staging`, and it does so on every commit to `main`. This is to ensure that we have a "golden" environment to point to, and can still test things out in an unstable space. To deploy locally to `unstable`: 

```bash
cf target -o cisa-getgov-prototyping -s unstable
cf push getgov-unstable -f ops/manifests/manifest-unstable.yaml
cf run-task getgov-unstable --command 'python manage.py migrate' --name migrate
```
