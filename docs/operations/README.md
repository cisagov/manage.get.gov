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

We have three types of environments: developer "sandboxes", `staging` and `stable`. Developers can deploy locally to their sandbox whenever they want. However, only our CD service can deploy to `staging` and `stable`, and it does so when we make tagged releases of `main`. For `staging`, this is done to ensure there is a non-production level test envirornment that can be used for user testing or for testing code before it is pushed to `stable`. `Staging` can be especially helpful when testing database changes or migrations that could have adververse affects in `stable`. On the other hand, `stable` is used to ensure that we have a "golden" environment to point to. We can refer to `stable` as our production environment and `staging` as our pre-production (pre-prod) environment. As such, code on main should always be tagged for `staging` before it is tagged for `stable`.

You should make sure all of the USWDS assets are compiled and collected before deploying to your sandbox. To deploy locally to `sandbox`:

For ease of use, you can run the `deploy.sh <sandbox name>` script in the `/src` directory to build the assets and deploy to your sandbox. Similarly, you could run `build.sh <sandbox name>` script to just compile and collect the assets without deploying.

Your sandbox space should've been setup as part of the onboarding process. If this was not the case, please have an admin follow the instructions [here](../../.github/ISSUE_TEMPLATE/developer-onboarding.md#setting-up-developer-sandbox).

## Serving static assets
We are using [WhiteNoise](http://whitenoise.evans.io/en/stable/index.html) plugin to serve our static assets on cloud.gov. This plugin is added to the `MIDDLEWARE` list in our apps `settings.py`.

Note that it’s a good idea to run `collectstatic` locally or in the docker container before pushing files up to your sandbox. This is because `collectstatic` relies on timestamps when deciding to whether to overwrite the existing assets in `/public`. Due the way files are uploaded, the compiled css in the `/assets/css` folder on your sandbox will have a slightly earlier timestamp than the files in `/public/css`, and consequently running `collectstatic` on your sandbox will not update `public/css` as you may expect. For convenience, both the `deploy.sh` and `build.sh` scripts will take care of that. 
