FROM python:3.14.10@sha256:a0362a0fda63931168dbae73de63cdffd798aa7a52c8cf7facaf2aec2c91238e

RUN apt-get update && apt-get install -y postgresql-client

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pip install pipenv
RUN pipenv sync --system --dev
