# Restoring Database with cloud.gov Instructions

The following doc has been copied from [a github gist](https://gist.github.com/markdboyd/8f20f9bdcfb591febaa838a50d0deb23) created by Mark Boyd at cloud.gov. It has been edited and added to this repo to ensure if that linked file ever goes away we can maintain our own instructions. Follow these instructions if you need to get a snapshot of a sandbox database onto _another_ sandbox. 

## Prerequisites

- Contact cloud.gov and request they put a snapshot of one sandbox onto another. Wait until this action is completed before running through the steps.

These utilities should be installed on your machine:

- `pg_dump`- Note this must much the version on production. Uninstall your current version before installing a new one
- `pg_restore`
- [`cf-service-connect`](https://github.com/cloud-gov/cf-service-connect)
- (Optional)`jq` - for formatting jsons

Note: If you can't install these on your device you can isntead add them to a docker container

## Creating a database backup using provided credentials

1. Get the GUID of the of the user-provided service:

    ```shell
    cf service <service-name> --guid
    ```

    where:
    - `service-name`: is the service you are trying to connect to
    _Example_

    ```shell
    cf service getgov-stable-restore-test  --guid
    ```

    service-name: is the service
2. View the database credentials from the user-provided service created by cloud.gov support:

    ```shell
    cf curl "/v3/service_instances/<service-guid>/credentials" | jq 
    ```

    where:

    - `service-guid`: GUID of the user provided service from the previous step

    Note: If this fails for jq and you can't install jq, just remove the `| jq` part.

3. Create a tunnel

    ```shell
    cf ssh -L <55432>:<host>:<port> YOUR-HOST-APP
    ```

    where:

    - `55432`: any local port not in use on your local machine for the SSH tunnel, this port will be used in the next step
    - `host` - Database host from the credentials in the previous step
    - `port` - Database port from the credentials in the previous step
    - `YOUR-HOST-APP` - App that you want to use for the tunneling

    You should see output indicating a SSH session is open with the app. **Leave this session open in this terminal window or else the tunnel will no longer be open.**

4. In a separate terminal window, create a database dump:

   ```shell
    $ pg_dump -F c --no-acl --no-owner -f backup.pg postgresql://USERNAME:PASSWORD@localhost:PORT/NAME
   ```

   where:

   - `USERNAME` - database username from credentials in step 2
   - `PASSWORD` - database password from credentials in step 2
   - `PORT` - port used for tunneling in step 3
   - `NAME` - database name from credentials in step 2

## Restoring backup to a local database

This is great if you are having trouble connecting via an app

1. Import the database backup into a local database:

    ```shell
    pg_restore --create --clean --no-owner --if-exists --dbname=<local-db-name> -h localhost backup.pg
    ```
    
    where:
    
    - `local-db-name` - Name of database where you want to import data locally

## Creating a new database to put the database in (Reccomended)

1. Create a new database service that will be used to import the backup:

    ```shell
    cf create-service aws-rds micro-psql <service-name>
    ```

2. Bind the database service to a running app:


    ```shell
    cf bind-service <app> <service-name>
    ```
    
    where:
    
    - `app` - any running app for binding the database
    - `service-name` - the name of the database service for importing the backup 

## Restoring the backup into an exising or new database

1. With your new database or existing database use `cf connnect-to-service` to open a tunnel to it:

    ```shell
    cf connect-to-service -no-client <app> <service-name>
    ```

    where:

    - `app` - the app used for binding the database in the previous step
    - `service-name` - the name of the database service for importing the backup 

    _Example_:

    ```shell
    cf connect-to-service -no-client getgov-backup getgov-backup-database
    ```

    _You should see console output something like_:

    ```shell
    Finding the service instance details...
    Setting up SSH tunnel...
    SSH tunnel created.
    Skipping call to client CLI. Connection information:

    Host: localhost
    Port: <port>
    Username: <username>
    Password: <password>
    Name: <db-name>

    Leave this terminal open while you want to use the SSH tunnel. Press Control-C to stop.
    ```

2. Import the database backup into the desired database service.

    On Linux/Mac:

    ```shell
    pg_restore --create --clean --no-owner --if-exists \
        --dbname=<db-name> \
        -h localhost \
        -p <port> \
        -U <username> backup.pg
    ```

    On Windows:

    ```shell
    pg_restore --create --clean --no-owner --if-exists^
        --dbname=<db-name>^
        -h localhost^
        -p <port>^
        -U <username> backup.pg    
    ```

    where:

    - `db-name` - Database name from console output in previous step
    - `port` - Port for tunnel from console output in previous step
    - `username` - Database username for database service from console output in previous step

    _Note:_ for a large database this could take up to 5 mins to run
3. Once the database import is complete, use `connect-to-service` again to open a database CLI session where you can query the imported data and verify that it is correct:

    ```shell
    cf connect-to-service <app> <service-name>    
    ```

## Reload user fixtures

Once you move data from one sandbox to another you may lose fixture data resulting in people losing access to admin. To handle that:
1. ssh into the sandbox and start a shell 
    ```shell
    ssh getgov-<env> 
    /tmp/lifecylce/shell
    ./manage.py shell
    ```

2. In the python shell run the following to load user fixtures
 ```
 from fixutres_user.py import UserFixture
 UserFixture.load()
 ```