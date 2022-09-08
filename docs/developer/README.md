# Development
========================

If you're new to Django, see [Getting Started with Django](https://www.djangoproject.com/start/) for an introduction to the framework.

## Local Setup

* Install Docker <https://docs.docker.com/get-docker/>
* Initialize the application:

  ```shell
  cd src
  docker-compose build
  ```
* Run the server: `docker-compose up`

  Press Ctrl-c when you'd like to exit or pass `-d` to run in detached mode.

Visit the running application at [http://localhost:8080](http://localhost:8080).

## Setting Vars

Every environment variable for local development is set in [src/docker-compose.yml](../../src/docker-compose.yml).

Including variables which would be secrets and set via a different mechanism elsewhere.

## Viewing Logs

If you run via `docker-compose up`, you'll see the logs in your terminal.

If you run via `docker-compose up -d`, you can get logs with `docker-compose logs -f`.

You can change the logging verbosity, if needed. Do a web search for "django log level".

## Running tests

Crash course on Docker's `run` vs `exec`: in order to run the tests inside of a container, a container must be running. If you already have a container running, you can use `exec`. If you do not, you can use `run`, which will attempt to start one.

To get a container running:

```shell
cd src
docker-compose build
docker-compose up -d
```

Django's test suite:

```shell
docker-compose exec app ./manage.py test
```

OR

```shell
docker-compose exec app python -Wa ./manage.py test  # view deprecation warnings
```

Linters:

```shell
docker-compose exec app ./manage.py lint
```
