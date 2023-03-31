FROM python:3.10

# Python 3.11 introduces a bug in oic package, fyi - Oct 31, 2022

RUN apt-get update && apt-get install -y postgresql-client

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pip install pipenv
RUN pipenv sync --system --dev
