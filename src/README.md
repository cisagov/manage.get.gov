# Registrar
========================

## Development

If you're new to Django, see [Getting Started with Django](https://www.djangoproject.com/start/) for an introduction to the framework.

### Local Setup

* Install Docker <https://docs.docker.com/get-docker/>
* Initialize the application:

  ```shell
  docker-compose build
  ```
* Run the server: `docker-compose up`

### Update Dependencies

1. Check the [Pipfile](./src/Pipfile) for pinned dependencies and manually adjust the version numbers
1. Run `docker-compose up` and `docker-compose exec app pipenv update` to perform the upgrade and generate a new [Pipfile.lock](./src/Pipfile.lock) 