# Working with Cloud.gov Databases

You can connect to a Cloud.gov database using the
[cf-service-connect](https://github.com/cloud-gov/cf-service-connect) plugin.
After installing it, use the command

```shell
cf connect-to-service getgov-ENVIRONMENT getgov-ENVIRONMENT-databse
```

to get a `psql` shell on the sandbox environment's database.

## Running Migrations

When new code changes the database schema (ie, you change a model or pull some
code that has), we need to apply Django's migrations.

### On Local

```shell
docker-compose exec app bash
./manage.py makemigrations
```

Then perform docker-compose down & docker-compose up to run with the new migrations.

### On Cloud.gov

We can run these using CloudFoundry's tasks to run the `manage.py migrate`
command in the correct environment. For any developer environment, developers
can manually run the task with

```shell
cf run-task getgov-ENVIRONMENT --wait --command 'python manage.py migrate' --name migrate
```

(The optional 'wait' argument will wait until the environment is stable)

Optionally, load data from fixtures as well

```shell
cf run-task getgov-ENVIRONMENT --wait --command 'python manage.py load' --name loaddata
```

For the `stable` or `staging` environments, developers don't have credentials so we need to run that command using Github Actions. Go to
<https://github.com/cisagov/getgov/actions/workflows/migrate.yaml> and select
the "Run workflow" button, making sure that `stable` or `staging` depending on which envirornment you desire to update.

## Getting data for fixtures

To run the `dumpdata` command, you'll need to ssh to a running container. `cf run-task` is useless for this, as you will not be able to see the output.

```shell
cf ssh getgov-ENVIRONMENT
/tmp/lifecycle/shell  # this configures your environment
./manage.py dumpdata
```

## Access certain table in the database
1. `cf connect-to-service getgov-ENVIRONMENT getgov-ENVIRONMENT-database` gets you into whichever environments database you'd like
2. `\c [table name here that starts cgaws...etc];` connects to the [cgaws...etc] table
3. `\dt` retrieves information about that table and displays it
4. Make sure the table you are looking for exists. For this example, we are looking for `django_migrations`
5. Run `SELECT * FROM django_migrations;` to see everything that's in it!

## Dropping and re-creating the database

For your sandbox environment, it might be necessary to start the database over from scratch.
The easiest way to do that is `DROP DATABASE ...` followed by `CREATE DATABASE
...`. In the `psql` shell, first run the `\l` command to see all of the
databases that are present:

```shell
cgawsbrokerprodyaobv93n2g3me5i=> \l
                                                        List of databases
              Name              |      Owner       | Encoding |   Collate   |    Ctype    |           Access privileges
--------------------------------+------------------+----------+-------------+-------------+---------------------------------------
 cgawsbrokerprodyaobv93n2g3me5i | ugsyn42g56vtykfr | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
 postgres                       | ugsyn42g56vtykfr | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
...
```

You will need the name of the database beginning with `cgawsbroker...` for the
next step. To drop that database, you first have to connect to a different
database (you can't drop the database that you are connected to). We connect to
the default `postgres` database instead

```shell
cgawsbrokerprodyaobv93n2g3me5i=> \c postgres;
psql (14.4, server 12.11)
SSL connection (protocol: TLSv1.2, cipher: ECDHE-RSA-AES256-GCM-SHA384, bits: 256, compression: off)
You are now connected to database "postgres" as user "ugsyn42g56vtykfr".
```

Now drop and create the database with the name above.

```shell
postgres=> DROP DATABASE cgawsbrokerprodyaobv93n2g3me5i;
DROP DATABASE
postgres=> CREATE DATABASE cgawsbrokerprodyaobv93n2g3me5i;
CREATE DATABASE
```

Now the database is empty and Django will need to re-run all of its migrations
in order for the app to start again.

### Warnings

This is a very intrusive procedure and it can go wrong in a number of ways.
For example, if the running cloud.gov application goes down, the
`connect-to-service` SSH tunnel will go away and if the app can't come back up
(say, because the database has been dropped but not created) then it isn't
possible to SSH back into the database to fix it and the Cloudfoundry
resources may have to be completely deleted and re-created.
