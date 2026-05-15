# HOWTO Update Python 
========================

## HOWTO update Python Dependencies

1. Check the [Pipfile](../../../src/Pipfile) for pinned dependencies and manually adjust the version numbers
2. Run `docker compose stop` to spin down the current containers and images so we can start afresh
3. Run:

```bash
cd src
docker-compose run app bash -c "pipenv lock && pipenv requirements > requirements.txt"
```

This will generate a new [Pipfile.lock](../../../src/Pipfile.lock) and create a new [requirements.txt](../../../src/requirements.txt). It will not install anything.

It is necessary to use `bash -c` because `run pipenv requirements` will not recognize that it is running non-interactively and will include garbage formatting characters.

The requirements.txt is used by Cloud.gov. It is needed to work around a bug in the CloudFoundry buildpack version of Pipenv that breaks on installing from a git repository.
4. Run `docker-compose build` to build a new image for local development with the updated dependencies.

The reason for de-coupling the `build` and `lock` steps is to increase consistency between builds--a run of `build` will always get exactly the dependencies listed in `Pipfile.lock`, nothing more, nothing less.

========================

## HOWTO update the Python Version

If you're updating the Python version, follow the following steps:

1. Update [Pipfile's](../../../src/Pipfile) `python_version` to the correct version. This line will tell `pipenv` to warn if the Python interpreter version doesn't match.

2. Update the [Dockerfile](../../../src/Dockerfile) to the correct version. This updates the base image tag to the new Python version.
3. Run `docker compose down` to spin down the current containers and images so we can start afresh
3. Run `docker compose build` rebuild the container with a new image with the new python version. Note this will still be using the old pipfile.lock, which means if there are completely imcompatible dependencies you will start to see errors or warnings. Watch for these errors but don't troubleshoot yet, you're not done.
4. Now that we have a new container, we can update all the requirements. This may  automatically remove errors and warnings you saw in the last step. Run: 

```bash
cd src
docker-compose run app bash -c "pipenv lock && pipenv requirements > requirements.txt"
```

5. Run docker-compose build a second time to pick up the freshly generated lock file

7. Trouble shoot any errors or warnings that didn't go away on the build or which pop-up when testing the app.

