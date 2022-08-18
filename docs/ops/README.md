# Operations
========================

## Authenticating

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

## Rotating Environment Secrets

Secrets were originally created with:

```sh
cf cups getgov-credentials -p credentials-<ENVIRONMENT>.json
```

Where `credentials-<ENVIRONMENT>.json` looks like:

```json
{
  "DJANGO_SECRET_KEY": "EXAMPLE",
  ...
}
```

You can see the current environment with `cf env <APP>`, for example `cf env getgov-dev`.

The command `cups` stands for [create user provided service](https://docs.cloudfoundry.org/devguide/services/user-provided.html). User provided services are the way currently recommended by Cloud.gov for deploying secrets. The user provided service is bound to the application in `manifest-<ENVIRONMENT>.json`.

To rotate secrets, create a new `credentials-<ENVIRONMENT>.json` file, upload it, then restage the app.

Example:

```bash
cf uups getgov-credentials -p credentials-unstable.json
cf restage getgov-dev --strategy rolling
```

Non-secret environment variables can be declared in `manifest-<ENVIRONMENT>.json` directly.

## Database

In sandbox, created with `cf create-service aws-rds micro-psql getgov-database`.

Binding the database in `manifest-<ENVIRONMENT>.json` automatically inserts the connection string into the environment as `DATABASE_URL`.

[Cloud.gov RDS documentation](https://cloud.gov/docs/services/relational-database/).