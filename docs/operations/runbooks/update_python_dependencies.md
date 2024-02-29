# HOWTO Update Python Dependencies
========================

1. Check the [Pipfile](../../../src/Pipfile) for pinned dependencies and manually adjust the version numbers
2. Run `docker-compose stop` to spin down the current containers and images so we can start afresh
2. Run

        cd src
        docker-compose run app bash -c "pipenv lock && pipenv requirements > requirements.txt"

    This will generate a new [Pipfile.lock](../../../src/Pipfile.lock) and create a new [requirements.txt](../../../src/requirements.txt). It will not install anything.

    It is necessary to use `bash -c` because `run pipenv requirements` will not recognize that it is running non-interactively and will include garbage formatting characters.

    The requirements.txt is used by Cloud.gov. It is needed to work around a bug in the CloudFoundry buildpack version of Pipenv that breaks on installing from a git repository.
3. Change geventconnpool back to what it was originally within the Pipfile.lock and requirements.txt.
    This is done by either saving what it was originally or opening a PR and using that as a reference to undo changes to any mention of geventconnpool.
    Geventconnpool, when set as a requirement without the reference portion, is defaulting to get a commit from 2014 which then breaks the code, as we want the newest version from them. 
4. Run `docker-compose build` to build a new image for local development with the updated dependencies.

    The reason for de-coupling the `build` and `lock` steps is to increase consistency between builds--a run of `build` will always get exactly the dependencies listed in `Pipfile.lock`, nothing more, nothing less.