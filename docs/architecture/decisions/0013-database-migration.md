# 13. Use CloudFoundry tasks and Github Actions to manually run migrations

Date: 2022-10-04

## Status

Accepted

## Context

A database-backed web application needs a way to change the “schema” or
structure of the database (adding/dropping tables, adding/dropping/altering
columns of tables). These changes are called “migrations”. They are checked-in
to the Github repository along with the code that uses the changed database.
When that new code is deployed, it will usually run, but may give errors until
the matching migrations have been applied to the database.

## Decision

We will not run the checked-in migrations automatically as part of deploys. We
will manually apply database migrations to our Cloud.gov environments using
Cloudfoundry’s `run-task` command to run Django’s `manage.py migrate` command.
For the `unstable` environment, we can run the `cf run-task . . .` command
directly. For the `staging` environment we have a Github Actions workflow
called “Run Migrations”
<https://github.com/cisagov/getgov/actions/workflows/migrate.yaml> that will
run that `cf` command using the credentials for `staging` that are only in the
Github Actions configuration. 

## Consequences

Not automatically applying database migrations before running new code means
that the site might stop working briefly until the database migrations are
applied. This trade-off feels worth the gain in control that we get by not
having migrations run unexpectedly.

Some of these consequences could be mitigated by developer attention to the
impacts in the unstable and/or staging environment.