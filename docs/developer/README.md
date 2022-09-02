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

Django's test suite:

```shell
docker-compose up -d
docker-compose exec app ./manage.py test
docker-compose stop
```

Linters:

```shell
docker-compose up -d
docker-compose exec app ./manage.py test
docker-compose stop
```

(Starting a container manually is optional. You can also use `docker-compose run` which will start the container for you. That method is slower, which is why you may prefer `exec` if you already have the application running.)