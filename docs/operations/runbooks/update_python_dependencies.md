# HOWTO Update Python Dependencies
========================

1. Check the [Pipfile](./src/Pipfile) for pinned dependencies and manually adjust the version numbers
1. Run `cd src`, `docker-compose up -d`, and `docker-compose exec app pipenv update` to perform the upgrade and generate a new [Pipfile.lock](./src/Pipfile.lock) 
1. (optional) Run `docker-compose stop` and `docker-compose build` to build a new image for local development with the updated dependencies.

The reason for de-coupling the `build` and `update` steps is to increase consistency between builds and reduce "it works on my laptop!". Therefore, `build` uses the lock file as-is; dependencies are never updated except by explicit choice.