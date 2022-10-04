# HOWTO Rotate the Application's Secrets
========================

Secrets are read from the running environment.

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

You can see the current environment with `cf env <APP>`, for example `cf env getgov-unstable`.

The commands `cups` and `uups` stand for [`create user provided service`](https://docs.cloudfoundry.org/devguide/services/user-provided.html) and `update user provided service`. User provided services are the way currently recommended by Cloud.gov for deploying secrets. The user provided service is bound to the application in `manifest-<ENVIRONMENT>.json`.

To rotate secrets, create a new `credentials-<ENVIRONMENT>.json` file, upload it, then restage the app.

Example:

```bash
cf update-user-provided-service getgov-credentials -p credentials-unstable.json
cf restage getgov-unstable --strategy rolling
```

Non-secret environment variables can be declared in `manifest-<ENVIRONMENT>.json` directly.